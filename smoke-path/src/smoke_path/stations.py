"""Measured air quality from monitoring stations (OpenAQ v3: CPCB and other reference monitors).

Used as the fallback source of the "Live air" tabs when CPCB's own feed (cpcb.py) is not
available. OpenAQ often receives CPCB readings about 2 days late; readings up to MAX_AGE_H
old are used and their age is shown.

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
MAX_AGE_H = 72  # readings older than this are not used (CAMS grid keeps 3 past days to compare with)
MAX_STATIONS = 40  # keeps us far below OpenAQ's 60 requests a minute
CELL_DEG = 0.25  # one station per cell (Delhi alone has ~40)
WORKERS = 8


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
