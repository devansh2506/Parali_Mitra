"""Measured air quality from monitoring stations (OpenAQ v3, the only station source).

It feeds the "Live air" tabs. OpenAQ often receives the government stations' readings 2-4 days late; readings up to MAX_AGE_H
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
# OpenAQ parameter ids, all in µg/m³ (OpenAQ also lists ppb/ppm versions of the gases; those are ignored).
PARAMETERS = {2: "pm2_5", 1: "pm10", 5: "no2", 6: "so2", 4: "co", 3: "o3"}
# CPCB stations on OpenAQ: the live gas sensors are labelled "ppb" but hold CPCB's own units (CO in mg/m³,
# NO2 and SO2 in µg/m³): CO "ppb" values are ~0.1-4 across stations (real CO would be hundreds of ppb), and the
# correctly labelled µg/m³ gas sensors there stopped in 2018. So for CPCB only: id -> (pollutant, factor to µg/m³).
CPCB_AS_LABELLED_PPB = {102: ("co", 1000), 15: ("no2", 1), 101: ("so2", 1)}
PARTICLES = ("pm2_5", "pm10")
MAX_VALUE = {"pm2_5": 2000, "pm10": 2000, "no2": 2000, "so2": 2000, "o3": 2000, "co": 60000}  # above this: sensor error
TIMEOUT_S = 8
MAX_AGE_H = 120  # readings older than this are not used. OpenAQ gets CPCB readings 3-5 days late at times; the age is always shown
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
    """bbox = (south, west, north, east). Reference monitors measuring PM2.5 or PM10 (their gas sensors come along)."""
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
        sensors, scale = {}, {}
        is_cpcb = ((loc.get("provider") or {}).get("name") or "").strip().upper() == "CPCB"
        for s in loc.get("sensors") or []:
            pid = (s.get("parameter") or {}).get("id")
            if s.get("id") is None:
                continue
            if pid in PARAMETERS:
                sensors[s["id"]] = PARAMETERS[pid]
            elif is_cpcb and pid in CPCB_AS_LABELLED_PPB:
                sensors[s["id"]], scale[s["id"]] = CPCB_AS_LABELLED_PPB[pid]
        if any(v in PARTICLES for v in sensors.values()):
            out.append({
                "id": loc.get("id"), "name": loc.get("name") or "", "lat": lat, "lon": lon, "last": last,
                "provider": ((loc.get("provider") or {}).get("name") or ""), "sensors": sensors, "scale": scale,
            })
    return out


def pick(locations, limit=MAX_STATIONS, cell=CELL_DEG):
    """At most one station per cell (the one measuring most pollutants, then the most recent), at most `limit` in all."""
    best = {}
    rank = lambda loc: (len(set(loc["sensors"].values())), loc["last"])  # noqa: E731
    for loc in locations:
        k = (math.floor(loc["lat"] / cell), math.floor(loc["lon"] / cell))
        if k not in best or rank(loc) > rank(best[k]):
            best[k] = loc
    return sorted(best.values(), key=lambda x: x["last"], reverse=True)[:limit]


def parse_latest(data, loc, now, max_age_h=MAX_AGE_H):
    """One station's latest readings: {name, lat, lon, time, provider, pm2_5, pm10, no2, so2, co, o3} or None."""
    out = {"id": loc["id"], "name": loc["name"], "provider": loc["provider"], "lat": loc["lat"], "lon": loc["lon"],
           "time": None, **{p: None for p in PARAMETERS.values()}}
    newest = {}
    for r in (data or {}).get("results") or []:
        pollutant = loc["sensors"].get(r.get("sensorsId"))
        value, when = r.get("value"), _when(r.get("datetime"))
        if not pollutant or when is None or not isinstance(value, (int, float)) or value < 0 or value > MAX_VALUE[pollutant]:
            continue  # unknown sensor, bad or negative value
        if now - when > timedelta(hours=max_age_h):
            continue
        if pollutant in newest and newest[pollutant] >= when:
            continue  # the same pollutant from two sensors: keep the newer reading
        newest[pollutant] = when
        out[pollutant] = float(value) * loc.get("scale", {}).get(r.get("sensorsId"), 1)
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
