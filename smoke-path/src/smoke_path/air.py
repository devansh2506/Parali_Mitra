"""Predicted air quality: the CAMS forecast exactly as Open-Meteo serves it, as India's AQI.

No model of our own is added: no fire plumes, no station correction. The grid covers
Punjab, Haryana, Delhi and north Rajasthan (lat 26-34.4, lon 70.4-80) at CAMS's own 0.4 degrees,
from one day back (for 24 hour averages) to 3 days ahead, and is reused for AQ_TTL_S.
"""

import time
from datetime import timedelta

from . import airquality
from .net import ApiError

REGION_GRID = {"south": 26.0, "west": 70.4, "step": 0.4, "rows": 22, "cols": 25}
PAST_DAYS = 1
FORECAST_DAYS = 3
AQ_TTL_S = 3 * 3600  # CAMS updates twice a day; Open-Meteo counts each grid point as a call
OVERLAY_STEP_H = 3
OUTLOOK_HOURS = 48

_cache = {}


def cached(key, make, ttl_s, clock=time.monotonic):
    """make() once per ttl_s for this key (per Lambda instance); errors are not cached."""
    now = clock()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = make()
    for k in [k for k, v in _cache.items() if v[0] <= now]:
        del _cache[k]
    _cache[key] = (now + ttl_s, value)
    return value


def clear_cache():
    _cache.clear()


class AirUnavailable(Exception):
    """The CAMS forecast could not be fetched."""


def forecast_grid(api, now, clock=time.monotonic):
    """The CAMS FieldGrid for the region. Raises AirUnavailable."""
    try:
        return cached(("cams", now.date().isoformat()),
                      lambda: api.air_quality(REGION_GRID, PAST_DAYS, FORECAST_DAYS), AQ_TTL_S, clock)
    except (ApiError, ValueError) as err:
        raise AirUnavailable(str(err)) from None


def _hour(grid, t):
    return int(grid.hour_index(t) // 1)


def outlook(grid, lat, lon, now, hours=OUTLOOK_HOURS):
    """Hourly AQI and pollutants at a spot from now: [{t, aqi, category, dominant, pm2_5, ...}]."""
    h0 = _hour(grid, now)
    out = []
    for h in range(max(h0, 0), min(h0 + hours, grid.n_hours)):
        a = airquality.air_at(grid, lat, lon, h)
        if a:
            out.append({"t": (grid.t0 + timedelta(hours=h)).isoformat(timespec="minutes"), **a})
    return out


def overlay(grid, now, step_h=OVERLAY_STEP_H, hours=OUTLOOK_HOURS):
    """AQI on every grid node every step_h hours from now (for the map's time slider)."""
    h0 = max(_hour(grid, now), 0)
    times, values = [], []
    nodes = airquality.FieldGrid.points(grid.south, grid.west, grid.step, grid.rows, grid.cols)
    for h in range(h0, min(h0 + hours + 1, grid.n_hours), step_h):
        row = []
        for lat, lon in nodes:
            a = airquality.air_at(grid, lat, lon, h)
            row.append(a["aqi"] if a else None)
        times.append((grid.t0 + timedelta(hours=h)).isoformat(timespec="minutes"))
        values.append(row)
    return {"south": grid.south, "west": grid.west, "step": grid.step, "rows": grid.rows, "cols": grid.cols,
            "times": times, "aqi": values}
