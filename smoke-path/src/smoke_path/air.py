"""Predicted air quality at places on smoke paths: CAMS forecast + station correction + fire plumes.

prepare() fetches (or reuses, for CACHE_TTL_S) three things for the area the smoke covers:
  - the CAMS air-quality forecast on its 0.4 degree grid (Open-Meteo, no key)
  - the weather that spreads smoke: mixing height, 10 m wind, sunshine, cloud (Open-Meteo)
  - the latest station readings (OpenAQ, only with a key)
and returns an AirContext. Its methods give the `air` block for a place (AQI at an hour,
with the smoke from tracked fires added) and the 48 hour outlook for one spot.

Every part can fail on its own: no stations -> no correction; no weather -> no fire plumes
(CAMS only); no CAMS -> no air quality at all (the smoke paths still work).
"""

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import timedelta

from . import airquality, plume, stations
from .net import ApiError

log = logging.getLogger(__name__)

CACHE_TTL_S = 3600  # CAMS updates twice a day; stations hourly
OVERLAY_HOURS = (0, 6, 12, 24, 48)
OUTLOOK_HOURS = 48
PAST_DAYS = 3  # 24 hour averages for smoke that arrived up to a day before the fires were seen
FORECAST_DAYS = 3

_cache = {}


def _cached(key, make, clock=time.monotonic):
    now = clock()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = make()
    for k in [k for k, v in _cache.items() if v[0] <= now]:
        del _cache[k]
    _cache[key] = (now + CACHE_TTL_S, value)
    return value


def clear_cache():
    _cache.clear()


class AirUnavailable(Exception):
    """The CAMS forecast could not be fetched."""


@dataclass
class Source:
    """One fire whose smoke we spread: its traced path, emission rates (g/s) and burn time."""

    id: str
    path: list
    rates: dict
    start: object
    hours: float = plume.FIRE_HOURS


@dataclass
class AirContext:
    aq: airquality.FieldGrid
    met: object  # FieldGrid or None
    stations: list
    factors: list
    now: object
    notes: list = field(default_factory=list)

    def info(self):
        """What the air numbers are based on, for the page."""
        return {
            "forecast": "CAMS global (ECMWF), via Open-Meteo",
            "stations": len(self.stations),
            "corrected": bool(self.factors),
            "fire_plumes": self.met is not None,
            "forecast_from": self.aq.t0.isoformat(timespec="minutes"),
            "forecast_to": self.aq.end.isoformat(timespec="minutes"),
        }

    def hour(self, t):
        return math.floor(self.aq.hour_index(t))

    def correction(self, lat, lon):
        if not self.factors:
            return {}
        return {p: stations.correction_at(lat, lon, self.factors, p) for p in ("pm2_5", "pm10")}

    def extra(self, lat, lon, sources, only=None):
        """Smoke added by `sources` at (lat, lon): {pollutant: {hour index: µg/m³}}.

        only: {source id: (dist km, segment, fraction)} when the closest points are known.
        """
        out = {}
        if self.met is None:
            return out
        for src in sources:
            if not src.rates or not src.path:
                continue
            d, seg, f = only[src.id] if only and src.id in only else plume.nearest(lat, lon, src.path)
            t, km, speed = plume.along(src.path, seg, f)
            band = plume.CONE_START_KM + plume.CONE_GROWTH * km
            if d > 2 * band + 2:
                continue  # far outside the band: nothing measurable arrives
            mix = self.met.at("mix", t, lat, lon)
            cls = plume.stability(self.met.at("wind10", t, lat, lon), self.met.at("sun", t, lat, lon),
                                  self.met.at("cloud", t, lat, lon))
            for p, rate in src.rates.items():
                c = plume.concentration(rate, km, d, speed, mix, cls)
                if c >= 0.05:
                    plume.add_hours(out.setdefault(p, {}), self.aq.t0, t, src.hours, c)
        return out

    def at(self, lat, lon, t, extra=None):
        """`air` dict at the hour containing t."""
        return airquality.air_at(self.aq, lat, lon, self.hour(t), extra, self.correction(lat, lon))

    def outlook(self, lat, lon, extra=None, hours=OUTLOOK_HOURS):
        """Hourly AQI from now for `hours` hours: [{t, aqi, category, pm2_5, pm2_5_fires}]."""
        h0 = self.hour(self.now)
        corr = self.correction(lat, lon)
        out = []
        for h in range(h0, min(h0 + hours, self.aq.n_hours)):
            a = airquality.air_at(self.aq, lat, lon, h, extra, corr)
            if a:
                out.append({"t": (self.aq.t0 + timedelta(hours=h)).isoformat(timespec="minutes"), **a})
        return out

    def overlay(self):
        """AQI on the CAMS grid nodes at now + OVERLAY_HOURS (station-corrected, no fire plumes)."""
        h0 = self.hour(self.now)
        g = self.aq
        times, values = [], []
        for dh in OVERLAY_HOURS:
            h = h0 + dh
            if h >= g.n_hours:
                break
            row = []
            for lat, lon in airquality.FieldGrid.points(g.south, g.west, g.step, g.rows, g.cols):
                a = airquality.air_at(g, lat, lon, h, None, self.correction(lat, lon))
                row.append(a["aqi"] if a else None)
            times.append((g.t0 + timedelta(hours=h)).isoformat(timespec="minutes"))
            values.append(row)
        return {"south": g.south, "west": g.west, "step": g.step, "rows": g.rows, "cols": g.cols,
                "times": times, "aqi": values}

    def station_features(self):
        out = []
        for s in self.stations:
            sub = airquality.sub_index("pm2_5", s.get("pm2_5")) if s.get("pm2_5") is not None else None
            out.append({"lat": s["lat"], "lon": s["lon"],
                        "props": stations.station_feature_props(s, {"pm2_5_index": sub})})
        return out


def spec_around(latlons):
    """CAMS-aligned grids covering latlons: (air quality spec, weather spec)."""
    spec = airquality.grid_spec(latlons)
    return spec, spec


def prepare(api, now, aq_spec, met_spec, clock=time.monotonic):
    """AirContext for the area of aq_spec. Raises AirUnavailable without CAMS."""
    day = now.date().isoformat()
    key = tuple(sorted(aq_spec.items()))
    mkey = tuple(sorted(met_spec.items()))
    spec = aq_spec
    notes = []
    try:
        aq = _cached(("aq", key, day), lambda: api.air_quality(aq_spec, PAST_DAYS, FORECAST_DAYS), clock)
    except (ApiError, ValueError) as err:
        raise AirUnavailable(str(err)) from None
    try:
        met = _cached(("met", mkey, day), lambda: api.met(met_spec, PAST_DAYS, FORECAST_DAYS), clock)
    except (ApiError, ValueError) as err:
        log.warning("weather for plumes failed: %s", err)
        met = None
        notes.append("Smoke added by each fire could not be estimated (weather data missing); air quality is the CAMS forecast only.")
    found, factors = [], []
    if api.stations_available():
        bbox = (spec["south"], spec["west"], spec["south"] + (spec["rows"] - 1) * spec["step"],
                spec["west"] + (spec["cols"] - 1) * spec["step"])
        try:
            found = _cached(("st", key, now.strftime("%Y-%m-%dT%H")), lambda: api.stations(bbox, now), clock)
            factors = stations.factors(found, aq)
        except (ApiError, ValueError) as err:
            log.warning("OpenAQ failed: %s", err)
            notes.append("Monitoring stations could not be read; the forecast is not corrected by measurements.")
    return AirContext(aq=aq, met=met, stations=found, factors=factors, now=now, notes=notes)
