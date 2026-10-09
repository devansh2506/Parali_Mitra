"""Open-Meteo wind forecasts, wind vectors and time interpolation.

Forecast wind direction is where the wind comes FROM, in degrees clockwise
from north. Smoke moves the opposite way, so we store the vector the smoke
travels along:

    u = -speed * sin(dir)   (east, m/s)
    v = -speed * cos(dir)   (north, m/s)

We always interpolate (u, v) vectors, never angles: averaging 350 and 10
degrees as plain numbers gives 180, which points the wrong way.
"""

import bisect
import logging
import math
import os
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import IST
from .net import ApiError, parse_json, request

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
ENSEMBLE_MODEL = "icon_seamless_eps"  # ICON-EPS: global, hourly, 40 members, 7.5 days
ENSEMBLE_LEVEL = "10m"  # not every ensemble model has higher levels
TIMEZONE = "Asia/Kolkata"

FORECAST_TIMEOUT_S = 8
ENSEMBLE_TIMEOUT_S = 10
MAX_FORECAST_DAYS = 16
MAX_ENSEMBLE_DAYS = 7
MAX_PAST_DAYS = 3  # wind from up to 3 days ago, for tracing smoke from fires already seen

LEVELS = ("10m", "80m", "120m", "180m")
DEFAULT_LEVEL = "120m"  # smoke rises; 10 m wind is too low for a plume


class OutsideForecast(ValueError):
    """The requested time is not covered by the wind forecast (becomes a 400)."""


def wind_level():
    """Forecast height to use, from the WIND_LEVEL setting (default 120m)."""
    level = os.environ.get("WIND_LEVEL", DEFAULT_LEVEL).strip()
    if level not in LEVELS:
        log.warning("WIND_LEVEL=%r is not one of %s; using %s", level, LEVELS, DEFAULT_LEVEL)
        return DEFAULT_LEVEL
    return level


def wind_to_uv(speed, direction_deg):
    """Forecast (speed, FROM-direction) -> smoke motion vector (u east, v north)."""
    rad = math.radians(direction_deg)
    return -speed * math.sin(rad), -speed * math.cos(rad)


def _fmt(t):
    return f"{t.day} {t.strftime('%b')} {t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


class WindSeries:
    """Hourly smoke-motion vectors at one place, linearly interpolated in time."""

    def __init__(self, times, u, v):
        if not times:
            raise ApiError("The wind forecast has no values for this place")
        if not len(times) == len(u) == len(v):
            raise ApiError("The wind forecast arrays have different lengths")
        self.times = list(times)
        self.u = list(u)
        self.v = list(v)
        self._secs = [t.timestamp() for t in self.times]
        if any(b <= a for a, b in zip(self._secs, self._secs[1:])):
            raise ApiError("The wind forecast times are not in order")

    @property
    def start(self):
        return self.times[0]

    @property
    def end(self):
        return self.times[-1]

    def covers(self, t0, t1):
        return self._secs[0] <= t0.timestamp() and t1.timestamp() <= self._secs[-1]

    def at(self, t):
        """(u, v) at time t. Raises OutsideForecast if t is outside the forecast."""
        x = t.timestamp()
        secs = self._secs
        if x < secs[0] or x > secs[-1]:
            raise OutsideForecast(
                f"The wind forecast for this place covers {_fmt(self.start.astimezone(IST))} "
                f"to {_fmt(self.end.astimezone(IST))} (IST). Pick a burn time inside it."
            )
        i = bisect.bisect_right(secs, x) - 1
        if i >= len(secs) - 1:
            return self.u[-1], self.v[-1]
        f = (x - secs[i]) / (secs[i + 1] - secs[i])
        return (
            self.u[i] + f * (self.u[i + 1] - self.u[i]),
            self.v[i] + f * (self.v[i + 1] - self.v[i]),
        )


def _number(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def series_from_hourly(times, speeds, directions, tz=IST):
    """Build a WindSeries from Open-Meteo hourly arrays.

    Gaps inside the series are filled with the last good value. Missing values
    at the very start or end are dropped (so the series simply ends there)
    instead of being invented.
    """
    if not isinstance(times, list) or not isinstance(speeds, list) or not isinstance(directions, list):
        raise ApiError("The wind forecast is missing hourly data")
    if not len(times) == len(speeds) == len(directions):
        raise ApiError("The wind forecast arrays have different lengths")
    rows = []
    for t, s, d in zip(times, speeds, directions):
        try:
            when = datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
        except (TypeError, ValueError):
            raise ApiError(f"The wind forecast has a bad time value: {t!r}") from None
        s, d = _number(s), _number(d)
        rows.append((when, None if s is None or d is None else wind_to_uv(s, d)))
    good = [i for i, (_, uv) in enumerate(rows) if uv is not None]
    if not good:
        raise ApiError("The wind forecast has no values for this place")
    rows = rows[good[0] : good[-1] + 1]
    out_t, out_u, out_v = [], [], []
    last = None
    for when, uv in rows:
        if uv is None:
            uv = last  # fill a gap with the last good value
        last = uv
        out_t.append(when)
        out_u.append(uv[0])
        out_v.append(uv[1])
    return WindSeries(out_t, out_u, out_v)


def _tz_of(item):
    try:
        return timezone(timedelta(seconds=int(item.get("utc_offset_seconds", 19800))))
    except (TypeError, ValueError):
        return IST


def parse_forecast(data, level):
    """Open-Meteo forecast JSON (one object, or a list for many points) -> [WindSeries]."""
    items = data if isinstance(data, list) else [data]
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ApiError("The wind forecast reply has an unexpected shape")
        if item.get("error"):
            raise ApiError(f"The wind forecast failed: {item.get('reason', 'unknown reason')}")
        hourly = item.get("hourly")
        if not isinstance(hourly, dict):
            raise ApiError("The wind forecast reply has no hourly data")
        out.append(
            series_from_hourly(
                hourly.get("time"),
                hourly.get(f"wind_speed_{level}"),
                hourly.get(f"wind_direction_{level}"),
                _tz_of(item),
            )
        )
    return out


def _group_by_suffix(hourly, prefix):
    """{"": control values, "_member01": values, ...} for keys starting with `prefix`."""
    groups = {}
    for key, values in hourly.items():
        if key == prefix or key.startswith(prefix + "_"):
            groups[key[len(prefix) :]] = values
    return groups


def parse_ensemble(data, level=ENSEMBLE_LEVEL):
    """Open-Meteo ensemble JSON -> one WindSeries per member.

    Member keys look like `wind_speed_10m_member01`; we do not hard-code them.
    Keys are grouped by the suffix after the variable name, and members whose
    values are all null are skipped.
    """
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        raise ApiError("The ensemble reply has an unexpected shape")
    if data.get("error"):
        raise ApiError(f"The ensemble forecast failed: {data.get('reason', 'unknown reason')}")
    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        raise ApiError("The ensemble reply has no hourly data")
    times = hourly.get("time")
    speeds = _group_by_suffix(hourly, f"wind_speed_{level}")
    directions = _group_by_suffix(hourly, f"wind_direction_{level}")
    tz = _tz_of(data)
    members = []
    for suffix in sorted(set(speeds) & set(directions)):
        s, d = speeds[suffix], directions[suffix]
        if not isinstance(s, list) or not isinstance(d, list):
            continue
        if all(_number(x) is None for x in s) or all(_number(x) is None for x in d):
            continue
        members.append(series_from_hourly(times, s, d, tz))
    return members


def forecast_days_needed(end, today):
    """How many forecast days (counting today) are needed to reach `end`."""
    return (end.astimezone(IST).date() - today).days + 1


def past_days_needed(start, today):
    """How many days before today the wind data must start (0 for today or later)."""
    return max(0, (today - start.astimezone(IST).date()).days)


def forecast_url(points, days, level, past_days=0):
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
        "hourly": f"wind_speed_{level},wind_direction_{level}",
        "wind_speed_unit": "ms",
        "timezone": ",".join([TIMEZONE] * len(points)),
        "forecast_days": max(1, min(days, MAX_FORECAST_DAYS)),
    }
    if past_days > 0:
        params["past_days"] = min(past_days, MAX_PAST_DAYS)
    return FORECAST_URL + "?" + urllib.parse.urlencode(params, safe=",/")


def ensemble_url(lat, lon, days, past_days=0):
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "hourly": f"wind_speed_{ENSEMBLE_LEVEL},wind_direction_{ENSEMBLE_LEVEL}",
        "models": ENSEMBLE_MODEL,
        "wind_speed_unit": "ms",
        "timezone": TIMEZONE,
        "forecast_days": max(1, min(days, MAX_ENSEMBLE_DAYS + 1)),
    }
    if past_days > 0:
        params["past_days"] = min(past_days, MAX_PAST_DAYS)
    return ENSEMBLE_URL + "?" + urllib.parse.urlencode(params, safe=",/")


def fetch_forecast_raw(points, days, level, timeout=FORECAST_TIMEOUT_S, past_days=0):
    """Many points in ONE request. Returns the raw JSON bytes."""
    return request(forecast_url(points, days, level, past_days), timeout, name="Open-Meteo")


def fetch_ensemble_raw(lat, lon, days, timeout=ENSEMBLE_TIMEOUT_S, past_days=0):
    if days > MAX_ENSEMBLE_DAYS + 1:
        raise ApiError("The ensemble forecast only covers about 7 days")
    return request(ensemble_url(lat, lon, days, past_days), timeout, name="Open-Meteo ensemble")


def decode_forecast(body, level):
    return parse_forecast(parse_json(body, "Open-Meteo"), level)


def decode_ensemble(body):
    return parse_ensemble(parse_json(body, "Open-Meteo ensemble"))
