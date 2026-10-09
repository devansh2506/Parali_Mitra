"""Air quality: the CAMS forecast (via Open-Meteo) and India's AQI (CPCB National AQI).

CAMS is the Copernicus Atmosphere Monitoring Service global forecast run by ECMWF
(0.4 degree, ~45 km). It includes regional smoke, dust and city pollution, but its cells
are too coarse to see one village downwind of one field; plume.py adds that part.

The AQI follows CPCB's National Air Quality Index: a sub-index per pollutant from its
breakpoints, using the 24-hour average for PM2.5, PM10, NO2 and SO2 and the highest
8-hour average of the last 24 hours for CO and O3. The AQI is the highest sub-index,
and needs at least 3 pollutants including PM2.5 or PM10.
"""

import math
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import IST
from .net import ApiError, parse_json, request_open_meteo
from .wind import TIMEZONE, _coord

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
AQ_TIMEOUT_S = 20
CAMS_STEP = 0.4  # CAMS global grid spacing (degrees)
MAX_AQ_POINTS = 400
CHUNK_POINTS = 190  # points per request (3 requests for fire watch's 550 CAMS points), fetched in parallel
MAX_PAST_DAYS = 3
MAX_FORECAST_DAYS = 5

# Open-Meteo variable -> our short name. All in µg/m³ (CO too; CPCB uses mg/m³ for CO).
VARIABLES = {
    "pm2_5": "pm2_5",
    "pm10": "pm10",
    "carbon_monoxide": "co",
    "nitrogen_dioxide": "no2",
    "sulphur_dioxide": "so2",
    "ozone": "o3",
    "dust": "dust",  # desert dust (part of PM10); not an AQI pollutant, shown to explain high PM10
}
POLLUTANTS = ("pm2_5", "pm10", "co", "no2", "so2", "o3")  # the CPCB AQI pollutants we have
NAMES = {"pm2_5": "PM2.5", "pm10": "PM10", "co": "CO", "no2": "NO2", "so2": "SO2", "o3": "O3"}

# CPCB National AQI breakpoints: (concentration low, high) -> (index low, high).
# Concentrations in µg/m³, except CO in mg/m³. The top band is open-ended in CPCB's
# table; like CPCB's calculator we extend it linearly so it reaches 500 at the given value.
_BANDS = (0, 50, 100, 200, 300, 400, 500)
BREAKPOINTS = {
    "pm2_5": (0, 30, 60, 90, 120, 250, 380),
    "pm10": (0, 50, 100, 250, 350, 430, 510),
    "no2": (0, 40, 80, 180, 280, 400, 520),
    "so2": (0, 40, 80, 380, 800, 1600, 2400),
    "co": (0, 1.0, 2.0, 10, 17, 34, 51),
    "o3": (0, 50, 100, 168, 208, 748, 1000),
}
WINDOW_H = {"pm2_5": 24, "pm10": 24, "no2": 24, "so2": 24, "co": 8, "o3": 8}
AQI_MAX = 500

CATEGORIES = (  # (upper index, key, label, CPCB health impact)
    (50, "good", "Good", "Minimal impact."),
    (100, "satisfactory", "Satisfactory", "Minor breathing discomfort to sensitive people."),
    (200, "moderate", "Moderately polluted",
     "Breathing discomfort to people with lung disease such as asthma, and discomfort to people "
     "with heart disease, children and older adults."),
    (300, "poor", "Poor", "Breathing discomfort to most people on long exposure, and discomfort to people with heart disease."),
    (400, "very_poor", "Very poor",
     "Respiratory illness on long exposure. The effect may be stronger in people with lung and heart disease."),
    (AQI_MAX + 1, "severe", "Severe",
     "Affects healthy people and seriously affects those with lung or heart disease, even during light activity."),
)
CIGARETTE_PM25 = 22.0  # µg/m³ of PM2.5 for 24 h ~ 1 cigarette a day (Berkeley Earth, Muller & Muller 2015)


# ---- CPCB AQI ------------------------------------------------------------------------------


def sub_index(pollutant, conc):
    """CPCB sub-index for one pollutant (conc in µg/m³; CO converted to mg/m³ here)."""
    if conc is None:
        return None
    c = max(0.0, conc / 1000 if pollutant == "co" else conc)
    bp = BREAKPOINTS[pollutant]
    for i in range(1, len(bp)):
        if c <= bp[i] or i == len(bp) - 1:
            lo, hi = bp[i - 1], bp[i]
            value = _BANDS[i - 1] + (c - lo) * (_BANDS[i] - _BANDS[i - 1]) / (hi - lo)
            return min(AQI_MAX, round(value))
    return AQI_MAX


def category(aqi):
    for upper, key, label, advice in CATEGORIES:
        if aqi <= upper:
            return key, label, advice
    return CATEGORIES[-1][1:]


def averages(hourly, end):
    """CPCB averages at hour index `end` from hourly lists {pollutant: [...]}.

    24-hour mean for PM2.5, PM10, NO2, SO2; highest 8-hour mean within the last 24 hours
    for CO and O3. Needs at least 16 of the hours (CPCB's rule); otherwise None.
    """
    out = {}
    for p in POLLUTANTS:
        values = hourly.get(p)
        if not values:
            continue
        window = [v for v in values[max(0, end - 23): end + 1] if v is not None]
        if len(window) < 16:
            continue
        if WINDOW_H[p] == 24:
            out[p] = sum(window) / len(window)
        else:
            day = values[max(0, end - 23): end + 1]
            means = []
            for k in range(8, len(day) + 1):
                part = [v for v in day[k - 8: k] if v is not None]
                if len(part) >= 6:
                    means.append(sum(part) / len(part))
            if means:
                out[p] = max(means)
    return out


def aqi(averaged):
    """{"aqi", "category", "label", "dominant", "sub"} from CPCB-averaged concentrations, or None."""
    sub = {p: sub_index(p, c) for p, c in averaged.items() if c is not None}
    if len(sub) < 3 or not ({"pm2_5", "pm10"} & set(sub)):
        return None
    dominant = max(sub, key=lambda p: (sub[p], p in ("pm2_5", "pm10")))
    value = sub[dominant]
    key, label, _ = category(value)
    return {"aqi": value, "category": key, "label": label, "dominant": dominant, "sub": sub}


def driver_text(a):
    """What drives an `air` dict's AQI, in words: 'mostly PM10, largely desert dust'."""
    name = NAMES.get(a["dominant"], a["dominant"])
    if a["dominant"] == "pm10" and a.get("dust") and a.get("pm10") and a["dust"] >= 0.5 * a["pm10"]:
        return "mostly PM10, largely desert dust"
    return f"mostly {name}"


def cigarettes(pm25_24h):
    return round(pm25_24h / CIGARETTE_PM25, 1) if pm25_24h is not None else None


# ---- gridded hourly fields -----------------------------------------------------------------


class FieldGrid:
    """Hourly values of several variables on a regular lat/lon grid.

    values[var][node] is a list of hourly values starting at t0; nodes are row-major from
    the south-west corner. Space: bilinear between the 4 surrounding nodes (nearest edge
    outside). Time: linear between hours (first/last hour outside).
    """

    def __init__(self, south, west, step, rows, cols, t0, values):
        if rows < 2 or cols < 2:
            raise ValueError("FieldGrid needs at least 2x2 nodes")
        for var, nodes in values.items():
            if len(nodes) != rows * cols:
                raise ValueError(f"{var}: {len(nodes)} nodes for a {rows}x{cols} grid")
        self.south, self.west, self.step, self.rows, self.cols = south, west, step, rows, cols
        self.t0 = t0
        self.values = values
        self.n_hours = min(len(n) for nodes in values.values() for n in nodes) if values else 0

    @staticmethod
    def points(south, west, step, rows, cols):
        return [(south + r * step, west + c * step) for r in range(rows) for c in range(cols)]

    @property
    def end(self):
        return self.t0 + timedelta(hours=self.n_hours - 1)

    def hour_index(self, t):
        return (t - self.t0).total_seconds() / 3600

    def _corners(self, lat, lon):
        y = min(max((lat - self.south) / self.step, 0.0), self.rows - 1)
        x = min(max((lon - self.west) / self.step, 0.0), self.cols - 1)
        r0, c0 = min(int(y), self.rows - 2), min(int(x), self.cols - 2)
        fy, fx = y - r0, x - c0
        i = r0 * self.cols + c0
        return ((i, (1 - fy) * (1 - fx)), (i + 1, (1 - fy) * fx),
                (i + self.cols, fy * (1 - fx)), (i + self.cols + 1, fy * fx))

    def node_hours(self, var, lat, lon, h0, n):
        """Values at whole hours h0 .. h0+n-1 (hour indexes, clamped to the data)."""
        nodes = self.values[var]
        corners = self._corners(lat, lon)
        out = []
        for h in range(h0, h0 + n):
            k = min(max(h, 0), self.n_hours - 1)
            out.append(sum(w * nodes[i][k] for i, w in corners if w))
        return out

    def _prefix(self, var):
        """Per node running sums, so any window mean costs O(1)."""
        cache = self.__dict__.setdefault("_prefixes", {})
        if var not in cache:
            out = []
            for node in self.values[var]:
                run, acc = [0.0], 0.0
                for v in node[: self.n_hours]:
                    acc += v
                    run.append(acc)
                out.append(run)
            cache[var] = out
        return cache[var]

    def mean(self, var, lat, lon, a, b):
        """Mean over whole hours a..b (inclusive, clamped to the data) at (lat, lon)."""
        a, b = max(a, 0), min(b, self.n_hours - 1)
        if b < a:
            k = min(max(a, 0), self.n_hours - 1)
            return self.node_hours(var, lat, lon, k, 1)[0]
        pre = self._prefix(var)
        return sum(w * (pre[i][b + 1] - pre[i][a]) for i, w in self._corners(lat, lon) if w) / (b - a + 1)

    def value(self, var, lat, lon, h):
        return self.node_hours(var, lat, lon, h, 1)[0]

    def at(self, var, t, lat, lon):
        if self.n_hours == 1:
            return self.node_hours(var, lat, lon, 0, 1)[0]
        x = min(max(self.hour_index(t), 0.0), self.n_hours - 1)
        k = min(int(x), self.n_hours - 2)
        a, b = self.node_hours(var, lat, lon, k, 2)
        return a + (x - k) * (b - a)


def grid_to_json(grid):
    """A FieldGrid as plain JSON (saved fixtures)."""
    return {"south": grid.south, "west": grid.west, "step": grid.step, "rows": grid.rows, "cols": grid.cols,
            "t0": grid.t0.isoformat(), "values": grid.values}


def grid_from_json(doc):
    return FieldGrid(doc["south"], doc["west"], doc["step"], doc["rows"], doc["cols"],
                     datetime.fromisoformat(doc["t0"]), doc["values"])


def _fill(values):
    """Fill gaps with the last good value (leading gaps with the first good one)."""
    good = [v for v in values if v is not None]
    if not good:
        return None
    out, last = [], good[0]
    for v in values:
        last = v if v is not None else last
        out.append(last)
    return out


def _number(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def parse_hourly_points(data, variables, what):
    """Open-Meteo multi-point JSON -> (t0 aware datetime, {short: [[hourly] per point]}).

    `variables` maps Open-Meteo names to our short names. Every point must share the time axis.
    """
    items = data if isinstance(data, list) else [data]
    t0, times, out = None, None, {short: [] for short in variables.values()}
    for item in items:
        if not isinstance(item, dict):
            raise ApiError(f"The {what} reply has an unexpected shape")
        if item.get("error"):
            raise ApiError(f"The {what} failed: {item.get('reason', 'unknown reason')}")
        hourly = item.get("hourly")
        if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list) or not hourly["time"]:
            raise ApiError(f"The {what} reply has no hourly data")
        if times is None:
            times = hourly["time"]
            try:
                offset = timezone(timedelta(seconds=int(item.get("utc_offset_seconds", 19800))))
                t0 = datetime.strptime(times[0], "%Y-%m-%dT%H:%M").replace(tzinfo=offset)
            except (TypeError, ValueError):
                raise ApiError(f"The {what} has a bad time value: {times[0]!r}") from None
        elif hourly["time"] != times:
            raise ApiError(f"The {what} points have different hours")
        for name, short in variables.items():
            raw = hourly.get(name)
            if not isinstance(raw, list) or len(raw) != len(times):
                raise ApiError(f"The {what} is missing {name}")
            filled = _fill([_number(v) for v in raw])
            if filled is None:
                raise ApiError(f"The {what} has no {name} values for a point")
            out[short].append(filled)
    return t0.astimezone(IST), out


# ---- the CAMS forecast via Open-Meteo ------------------------------------------------------


def aq_url(points, past_days, forecast_days):
    params = {
        "latitude": ",".join(_coord(lat) for lat, _ in points),
        "longitude": ",".join(_coord(lon) for _, lon in points),
        "hourly": ",".join(VARIABLES),
        "domains": "cams_global",
        "timezone": TIMEZONE,
        "past_days": max(0, min(past_days, MAX_PAST_DAYS)),
        "forecast_days": max(1, min(forecast_days, MAX_FORECAST_DAYS)),
    }
    return AQ_URL + "?" + urllib.parse.urlencode(params, safe=",/")


def fetch_aq_raw(points, past_days, forecast_days, timeout=AQ_TIMEOUT_S):
    """Raw JSON bytes for up to CHUNK_POINTS points (one request)."""
    return request_open_meteo(aq_url(points, past_days, forecast_days), timeout, name="Open-Meteo air quality")


def grid_spec(latlons, pad=0.2, step=CAMS_STEP, max_points=MAX_AQ_POINTS):
    """A CAMS-aligned grid covering the given points: dict(south, west, step, rows, cols)."""
    lats = [p[0] for p in latlons]
    lons = [p[1] for p in latlons]
    while True:
        south = math.floor((min(lats) - pad) / step) * step
        west = math.floor((min(lons) - pad) / step) * step
        rows = max(2, math.ceil((max(lats) + pad - south) / step) + 1)
        cols = max(2, math.ceil((max(lons) + pad - west) / step) + 1)
        if rows * cols <= max_points:
            return {"south": round(south, 4), "west": round(west, 4), "step": round(step, 4), "rows": rows, "cols": cols}
        step *= 2  # still aligned with the CAMS grid


def decode_grid(raw_chunks, spec):
    """Raw replies (one per chunk, in order) -> FieldGrid of the six pollutants."""
    t0, merged = None, {short: [] for short in VARIABLES.values()}
    for raw in raw_chunks:
        t, part = parse_hourly_points(parse_json(raw, "Open-Meteo air quality"), VARIABLES, "air quality forecast")
        if t0 is None:
            t0 = t
        elif t != t0:
            raise ApiError("The air quality forecast parts start at different hours")
        for short, nodes in part.items():
            merged[short].extend(nodes)
    return FieldGrid(spec["south"], spec["west"], spec["step"], spec["rows"], spec["cols"], t0, merged)


def chunks(points, size=CHUNK_POINTS):
    return [points[i: i + size] for i in range(0, len(points), size)]


# ---- what a place gets ---------------------------------------------------------------------


def _window_extra(extra, a, b):
    return sum(v for k, v in extra.items() if a <= k <= b) if extra else 0.0


def air_at(grid, lat, lon, h, extra=None, corr=None):
    """Air at hour index h at (lat, lon): CAMS (times the station correction) plus extra smoke.

    extra: {pollutant: {hour index: µg/m³}} added by tracked fires; corr: {pollutant: factor}.
    Returns the `air` dict sent to the map, or None when the AQI cannot be formed.
    """
    extra, corr = extra or {}, corr or {}
    avg, now = {}, {}
    for p in POLLUTANTS:
        if p not in grid.values:
            continue
        f, ex = corr.get(p, 1.0), extra.get(p) or {}
        if WINDOW_H[p] == 24:
            a = max(h - 23, 0)
            avg[p] = grid.mean(p, lat, lon, a, h) * f + _window_extra(ex, a, h) / (h - a + 1)
        else:
            best = None
            for s in range(max(h - 23, 0), max(h - 6, 1)):
                e = min(s + 7, h)
                m = grid.mean(p, lat, lon, s, e) * f + _window_extra(ex, s, e) / (e - s + 1)
                best = m if best is None else max(best, m)
            avg[p] = best
        now[p] = grid.value(p, lat, lon, h) * f + ex.get(h, 0.0)
    result = aqi(avg)
    if result is None:
        return None
    fires_now = (extra.get("pm2_5") or {}).get(h, 0.0)
    return {
        "aqi": result["aqi"],
        "category": result["category"],
        "dominant": result["dominant"],
        "pm2_5": round(now["pm2_5"], 1),
        "pm2_5_fires": round(fires_now, 1),
        "pm2_5_24h": round(avg["pm2_5"], 1),
        "pm10": round(now["pm10"], 1) if "pm10" in now else None,
        "co": round(now["co"] / 1000, 2) if "co" in now else None,  # mg/m³ like CPCB
        "no2": round(now["no2"], 1) if "no2" in now else None,
        "so2": round(now["so2"], 1) if "so2" in now else None,
        "o3": round(now["o3"], 1) if "o3" in now else None,
        "dust": round(grid.value("dust", lat, lon, h), 1) if "dust" in grid.values else None,
        "cigarettes": cigarettes(avg["pm2_5"]),
    }


# ---- weather that spreads smoke (Open-Meteo forecast API) -----------------------------------

MET_URL = "https://api.open-meteo.com/v1/forecast"
MET_VARIABLES = {
    "boundary_layer_height": "mix",
    "wind_speed_10m": "wind10",
    "shortwave_radiation": "sun",
    "cloud_cover": "cloud",
}


def met_url(points, past_days, forecast_days):
    params = {
        "latitude": ",".join(_coord(lat) for lat, _ in points),
        "longitude": ",".join(_coord(lon) for _, lon in points),
        "hourly": ",".join(MET_VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": TIMEZONE,
        "past_days": max(0, min(past_days, MAX_PAST_DAYS)),
        "forecast_days": max(1, min(forecast_days, 16)),
    }
    return MET_URL + "?" + urllib.parse.urlencode(params, safe=",/")


def fetch_met_raw(points, past_days, forecast_days, timeout=AQ_TIMEOUT_S):
    return request_open_meteo(met_url(points, past_days, forecast_days), timeout, name="Open-Meteo weather")


def decode_met(raw_chunks, spec):
    t0, merged = None, {short: [] for short in MET_VARIABLES.values()}
    for raw in raw_chunks:
        t, part = parse_hourly_points(parse_json(raw, "Open-Meteo weather"), MET_VARIABLES, "weather forecast")
        if t0 is None:
            t0 = t
        elif t != t0:
            raise ApiError("The weather forecast parts start at different hours")
        for short, nodes in part.items():
            merged[short].extend(nodes)
    return FieldGrid(spec["south"], spec["west"], spec["step"], spec["rows"], spec["cols"], t0, merged)
