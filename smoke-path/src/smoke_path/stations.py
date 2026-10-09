"""Measured air quality from monitoring stations (OpenAQ v3: CPCB and other reference monitors).

Used twice:
1. The map shows each station's latest PM2.5 / PM10 reading.
2. The CAMS forecast is corrected near stations: where a station measures twice what
   CAMS says for that hour, nearby CAMS values are doubled (factor clamped to 0.5-3),
   fading back to no correction at CORRECTION_KM. The same factor is kept for the
   forecast hours (persistence of the current bias).

Needs a free OpenAQ API key (OPENAQ_API_KEY). Without it everything still works,
with no correction and no station dots.
"""

import logging
import math
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import IST
from .net import ApiError, parse_json, request
from .trajectory import KM_PER_DEG

log = logging.getLogger(__name__)

OPENAQ_URL = "https://api.openaq.org/v3"
PARAMETERS = {2: "pm2_5", 1: "pm10"}  # OpenAQ parameter ids
TIMEOUT_S = 8
MAX_AGE_H = 3  # readings older than this are not used
MAX_STATIONS = 40  # keeps us far below OpenAQ's 60 requests a minute
CELL_DEG = 0.25  # one station per cell (Delhi alone has ~40)
WORKERS = 8
CORRECTION_KM = 75.0
FACTOR_RANGE = (0.5, 3.0)


def api_key():
    # API key consumed here: OpenAQ v3 key from the OPENAQ_API_KEY env var.
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    return key or None


def _get(path, params, key, timeout=TIMEOUT_S):
    url = f"{OPENAQ_URL}{path}" + ("?" + urllib.parse.urlencode(params, safe=",") if params else "")
    try:
        raw = request(url, timeout, headers={"X-API-Key": key, "Accept": "application/json"}, name="OpenAQ")
    except ApiError as err:
        raise ApiError(str(err).replace(key, "***")) from None
    return raw


def fetch_locations_raw(bbox, key):
    """bbox = (south, west, north, east). Reference monitors measuring PM2.5 or PM10."""
    s, w, n, e = bbox
    params = {"bbox": f"{w:.4f},{s:.4f},{e:.4f},{n:.4f}", "parameters_id": "2,1", "monitor": "true", "limit": 1000}
    return _get("/locations", params, key)


def fetch_latest_raw(location_id, key):
    return _get(f"/locations/{int(location_id)}/latest", {"limit": 100}, key)


def _when(dt):
    try:
        return datetime.fromisoformat(str((dt or {}).get("utc")).replace("Z", "+00:00")).astimezone(IST)
    except (TypeError, ValueError):
        return None


def parse_locations(data, now, max_age_h=MAX_AGE_H):
    """Active monitors: [{id, name, provider, lat, lon, sensors {sensor id: pollutant}}]."""
    out = []
    for loc in (data or {}).get("results") or []:
        coords = loc.get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        last = _when(loc.get("datetimeLast"))
        if lat is None or lon is None or last is None or now - last > timedelta(hours=max_age_h):
            continue
        sensors = {}
        for s in loc.get("sensors") or []:
            pid = (s.get("parameter") or {}).get("id")
            if pid in PARAMETERS and s.get("id") is not None:
                sensors[s["id"]] = PARAMETERS[pid]
        if sensors:
            out.append({
                "id": loc.get("id"), "name": loc.get("name") or "", "lat": lat, "lon": lon, "last": last,
                "provider": ((loc.get("provider") or {}).get("name") or ""), "sensors": sensors,
            })
    return out


def pick(locations, limit=MAX_STATIONS, cell=CELL_DEG):
    """At most one station per cell (the most recently updated), at most `limit` in all."""
    best = {}
    for loc in locations:
        k = (math.floor(loc["lat"] / cell), math.floor(loc["lon"] / cell))
        if k not in best or loc["last"] > best[k]["last"]:
            best[k] = loc
    return sorted(best.values(), key=lambda x: x["last"], reverse=True)[:limit]


def parse_latest(data, loc, now, max_age_h=MAX_AGE_H):
    """One station's latest readings: {name, lat, lon, time, pm2_5, pm10, provider} or None."""
    out = {"id": loc["id"], "name": loc["name"], "provider": loc["provider"], "lat": loc["lat"], "lon": loc["lon"],
           "time": None, "pm2_5": None, "pm10": None}
    for r in (data or {}).get("results") or []:
        pollutant = loc["sensors"].get(r.get("sensorsId"))
        value, when = r.get("value"), _when(r.get("datetime"))
        if not pollutant or when is None or not isinstance(value, (int, float)) or value < 0 or value > 2000:
            continue  # unknown sensor, bad or negative value
        if now - when > timedelta(hours=max_age_h):
            continue
        out[pollutant] = float(value)
        out["time"] = max(out["time"], when) if out["time"] else when
    return out if out["time"] else None


def fetch_stations(bbox, key, now):
    """Latest readings for active monitors in bbox. Raises ApiError when the list fails."""
    locations = pick(parse_locations(parse_json(fetch_locations_raw(bbox, key), "OpenAQ"), now))
    if not locations:
        return []

    def one(loc):
        try:
            return parse_latest(parse_json(fetch_latest_raw(loc["id"], key), "OpenAQ"), loc, now)
        except ApiError as err:
            log.warning("OpenAQ station %s failed: %s", loc["id"], err)
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return [s for s in pool.map(one, locations) if s]


# ---- correcting CAMS -----------------------------------------------------------------------


def factors(stations, aq_grid):
    """Per station: measured / CAMS for PM2.5 and PM10 at the reading's hour (clamped)."""
    lo, hi = FACTOR_RANGE
    out = []
    for s in stations:
        row = {"lat": s["lat"], "lon": s["lon"]}
        for p in ("pm2_5", "pm10"):
            if s.get(p) is None:
                continue
            model = aq_grid.at(p, s["time"], s["lat"], s["lon"])
            if model and model > 1:
                row[p] = min(hi, max(lo, s[p] / model))
        if len(row) > 2:
            out.append(row)
    return out


def correction_at(lat, lon, station_factors, pollutant, max_km=CORRECTION_KM):
    """Factor to multiply CAMS by at (lat, lon): inverse-distance blend, fading to 1 at max_km."""
    num = den = 0.0
    nearest = math.inf
    coslat = math.cos(math.radians(lat))
    for f in station_factors:
        if pollutant not in f:
            continue
        d = math.hypot((f["lat"] - lat) * KM_PER_DEG, (f["lon"] - lon) * KM_PER_DEG * coslat)
        if d >= max_km:
            continue
        w = 1.0 / max(d, 1.0) ** 2
        num += w * f[pollutant]
        den += w
        nearest = min(nearest, d)
    if not den:
        return 1.0
    blended = num / den
    return 1.0 + (blended - 1.0) * (1.0 - nearest / max_km)


def station_feature_props(s, aqi_info=None):
    props = {"kind": "station", "name": s["name"], "provider": s["provider"],
             "time": s["time"].isoformat(timespec="minutes"),
             "pm2_5": None if s.get("pm2_5") is None else round(s["pm2_5"], 1),
             "pm10": None if s.get("pm10") is None else round(s["pm10"], 1)}
    if aqi_info:
        props.update(aqi_info)
    return props
