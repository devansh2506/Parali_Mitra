"""Run one smoke-path request from start to finish.

1. Pass 1: trace with the wind at the field only (Open-Meteo call 1).
2. Refine: fetch wind at the field + path points every 3 hours in ONE request
   (Open-Meteo call 2) and trace again using the nearest sampled site.
3. Band: cone puffs, or ensemble puffs when asked (ensemble call runs in the
   background from the start).
4. Places (Overpass) and fires (FIRMS) in parallel.

Only a failure of the wind forecast itself is fatal (502). Everything else
adds a note and the request still succeeds.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import IST, air, airquality, plume, report
from .apis import FIRE_SOURCES
from .ensemble import ensemble_puffs, member_lines, trace_members
from .net import ApiError
from .places import OVERPASS_TIMEOUT_S, locate
from .report import iso
from .trajectory import WindField, cone_puffs, hourly, refine_sites, single_site, trace
from .wind import OutsideForecast, forecast_days_needed, past_days_needed, wind_level

log = logging.getLogger(__name__)

# API Gateway HTTP APIs stop waiting after 30 s; finish well before that.
BUDGET_S = 25


def _sentence(text):
    return str(text).strip().rstrip(".") + "."


class WindUnavailable(Exception):
    """The wind forecast itself failed (becomes a 502)."""


@dataclass(frozen=True)
class SmokeRequest:
    lat: float
    lon: float
    start: datetime  # aware, IST
    hours: int
    uncertainty: str = "cone"
    origin: str = "field"  # "field": a planned burn; "fire": a fire already seen by satellite
    acres: float = 5.0  # field size for a planned burn (how much straw burns)
    frp: float = None  # a satellite fire's radiative power (MW), for origin "fire"
    fire_type: str = "farm"  # what was burning, for origin "fire"


@dataclass
class Result:
    report: dict
    cacheable: bool  # False when something optional failed for a reason that may pass
    places_checked: bool = True  # False when places failed or are incomplete


def run(
    req,
    api,
    *,
    level=None,
    now=None,
    budget_s=BUDGET_S,
    places_timeout_s=OVERPASS_TIMEOUT_S,
    clock=time.monotonic,
):
    level = level or wind_level()
    now = now or datetime.now(IST)
    deadline = clock() + budget_s

    def remaining(floor=0.1):
        return max(floor, deadline - clock())

    notes = []
    cacheable = True
    end = req.start + timedelta(hours=req.hours)
    today = now.astimezone(IST).date()
    days = max(1, forecast_days_needed(end, today))
    past = past_days_needed(req.start, today)  # > 0 when tracing a fire seen on an earlier day

    pool = ThreadPoolExecutor(max_workers=6)
    try:
        ens_future = None
        if req.uncertainty == "ensemble":
            ens_future = pool.submit(api.ensemble, req.lat, req.lon, days, past)

        # Pass 1: wind at the field only.
        try:
            field_series = api.forecast([(req.lat, req.lon)], days, level, past)[0]
        except ApiError as err:
            raise WindUnavailable(str(err)) from None
        path = trace(single_site(field_series), req.lat, req.lon, req.start, req.hours)

        # Pass 2: wind sampled along the first path, nearest site wins.
        sites = [(req.lat, req.lon)] + refine_sites(path)
        try:
            series = api.forecast(sites, days, level, past)
            field = WindField([(la, lo, s) for (la, lo), s in zip(sites, series)])
            path = trace(field.at, req.lat, req.lon, req.start, req.hours)
        except (ApiError, OutsideForecast) as err:
            log.warning("refine pass failed: %s", err)
            notes.append("Used the wind at your field only; wind along the path was unavailable.")
            cacheable = False

        # Band around the path.
        puffs = cone_puffs(path)
        members = []
        uncertainty = "cone"
        if ens_future is not None:
            try:
                member_series = ens_future.result(timeout=remaining())
                member_paths = trace_members(member_series, req.lat, req.lon, req.start, req.hours)
                puffs = ensemble_puffs(member_paths, centre_path=path)  # width from the ensemble
                members = member_lines(member_paths)
                uncertainty = "ensemble"
            except Exception as err:  # noqa: BLE001 - the ensemble is optional; fall back to the cone
                if isinstance(err, (TimeoutError, FutureTimeout)):
                    reason = "it took too long"
                elif isinstance(err, (ApiError, ValueError)):
                    reason = str(err).strip().rstrip(".") or "no usable members"
                else:
                    reason = "unexpected error"
                log.warning("ensemble failed: %r", err)
                notes.append(f"Forecast spread (ensemble) unavailable ({reason}); showing the simple cone instead.")
                cacheable = False

        # Places, fires and air quality in parallel.
        line = [(p.lat, p.lon) for p in hourly(path)]
        aq_spec, met_spec = air.spec_around(line)
        air_future = pool.submit(air.prepare, api, now, aq_spec, met_spec, clock)
        places_timeout = max(2.0, min(places_timeout_s, remaining() - 1.0))
        places_future = pool.submit(api.places, line, places_timeout)
        fire_futures = {}
        if api.fires_available():
            fire_futures = {s: pool.submit(api.fires, s, req.lat, req.lon) for s in FIRE_SOURCES}

        located = []
        places_checked = False
        try:
            found, note = places_future.result(timeout=remaining())
            located = locate(found, path, puffs)
            places_checked = note is None
            if note:
                notes.append(note)
                cacheable = False
        except (TimeoutError, FutureTimeout):
            notes.append("Places unavailable: OpenStreetMap took too long to answer.")
            cacheable = False
        except Exception as err:  # noqa: BLE001 - places are optional; never fail the request
            log.warning("places failed: %r", err)
            notes.append(_sentence(f"Places unavailable: {err if isinstance(err, ApiError) else 'unexpected error'}"))
            cacheable = False

        fire_list = []
        failed = []
        for source, future in fire_futures.items():
            try:
                fire_list.extend(future.result(timeout=remaining()))
            except Exception as err:  # noqa: BLE001 - fires are optional
                log.warning("fires %s failed: %r", source, err)
                failed.append((source, err if isinstance(err, ApiError) else "took too long or failed"))
        if not fire_futures:
            notes.append("Fires unavailable: no NASA FIRMS key is set (FIRMS_MAP_KEY).")
        elif len(failed) == len(fire_futures):
            notes.append(_sentence(f"Fires unavailable: {failed[0][1]}"))
            cacheable = False
        elif failed:
            notes.append("Some satellite fire data is missing (" + ", ".join(s for s, _ in failed) + ").")
            cacheable = False
        emission = _emission(req)
        best, air_info = None, None
        try:
            ctx = air_future.result(timeout=remaining())
            notes.extend(ctx.notes)
            air_info = ctx.info()
            src = air.Source("burn", path, emission["rates"], req.start) if emission["rates"] else None
            for p in located:
                if not p["in_band"]:
                    continue
                extra = ctx.extra(p["lat"], p["lon"], [src]) if src else {}
                pm = extra.get("pm2_5") or {}
                t = ctx.aq.t0 + timedelta(hours=max(pm, key=pm.get)) if pm else p["arrival"]
                a = ctx.at(p["lat"], p["lon"], t, extra)
                if a:
                    a["t"] = iso(t)
                    p["air"] = a
                    if best is None or a["pm2_5_fires"] > best["air"]["pm2_5_fires"]:
                        best = p
        except Exception as err:  # noqa: BLE001 - air quality is optional
            log.warning("air quality failed: %r", err)
            notes.append("Air quality could not be predicted right now (the CAMS forecast did not load).")
            cacheable = False
    finally:
        # Do not wait for slow background calls; the answer is ready.
        pool.shutdown(wait=False, cancel_futures=True)

    doc = report.build(
        lat=req.lat,
        lon=req.lon,
        start=req.start,
        hours=req.hours,
        path=path,
        puffs=puffs,
        members=members,
        located=located,
        fires=fire_list,
        notes=notes,
        wind_level=level,
        uncertainty=uncertainty,
        generated_at=now,
        places_checked=places_checked,
        origin=req.origin,
    )
    doc["air"] = air_info
    doc["emission"] = {k: v for k, v in emission.items() if k != "rates"}
    doc["emission"]["rates_g_s"] = {k: round(v, 2) for k, v in emission["rates"].items()} if emission["rates"] else None
    line = _air_line(emission, best)
    if line:
        doc["summary"].append(line)
    return Result(report=doc, cacheable=cacheable, places_checked=places_checked)


def _emission(req):
    """What the fire gives off: rates in g/s while it burns, and totals for the page."""
    if req.origin == "fire":
        rates = plume.rates_from_frp(req.frp, req.fire_type) if req.frp else None
        return {"source": "frp", "frp_mw": req.frp, "fire_type": req.fire_type, "hours": plume.FIRE_HOURS,
                "rates": rates, "pm2_5_kg": round(rates["pm2_5"] * plume.FIRE_HOURS * 3.6, 1) if rates else None}
    rates = plume.rates_from_area(req.acres)
    return {"source": "field", "acres": req.acres, "straw_burned_t": round(plume.burned_tonnes(req.acres), 1),
            "hours": plume.FIRE_HOURS, "rates": rates, "pm2_5_kg": round(rates["pm2_5"] * plume.FIRE_HOURS * 3.6, 1)}


def _air_line(emission, best):
    if not emission.get("pm2_5_kg"):
        return None
    if emission["source"] == "field":
        start = (f"Burning {emission['acres']:g} acres burns about {emission['straw_burned_t']:g} tonnes of straw "
                 f"and releases about {emission['pm2_5_kg']:.0f} kg of PM2.5")
    else:
        start = f"This fire releases about {emission['pm2_5_kg']:.0f} kg of PM2.5 an hour"
    if best is None or best["air"]["pm2_5_fires"] < 1:
        return start + "."
    a = best["air"]
    return (f"{start}; the most reaches {best['name']} (about +{a['pm2_5_fires']:.0f} µg/m³ of PM2.5, "
            f"AQI {a['aqi']} {airquality.category(a['aqi'])[1].lower()}).")
