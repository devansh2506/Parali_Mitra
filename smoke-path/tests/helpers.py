"""Shared test helpers: fake wind series and a fake API. No network anywhere."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smoke_path import IST, air  # noqa: E402
from smoke_path.airquality import FieldGrid  # noqa: E402
from smoke_path.net import ApiError  # noqa: E402
from smoke_path.wind import WindSeries, wind_to_uv  # noqa: E402

FIELD = (30.245, 75.844)
DAY0 = datetime(2026, 10, 10, 0, 0, tzinfo=IST)  # forecast starts here
START = datetime(2026, 10, 10, 14, 0, tzinfo=IST)  # burn time used in most tests
NOW = datetime(2026, 10, 10, 9, 0, tzinfo=IST)  # "now" for request checks


def hourly_times(n=72, t0=DAY0):
    return [t0 + timedelta(hours=h) for h in range(n)]


def const_series(speed, direction, n=72, t0=DAY0):
    """Constant wind: `speed` m/s blowing FROM `direction` degrees."""
    u, v = wind_to_uv(speed, direction)
    return WindSeries(hourly_times(n, t0), [u] * n, [v] * n)


def hourly_json(speeds, directions, level="120m", t0=DAY0):
    """An Open-Meteo-shaped forecast object for one point."""
    return {
        "latitude": FIELD[0],
        "longitude": FIELD[1],
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "hourly": {
            "time": [t.strftime("%Y-%m-%dT%H:%M") for t in hourly_times(len(speeds), t0)],
            f"wind_speed_{level}": speeds,
            f"wind_direction_{level}": directions,
        },
    }


def place(name, lat, lon, place_type="village", named=True):
    return {
        "name": name,
        "name_local": "",
        "place_type": place_type,
        "named": named,
        "lat": lat,
        "lon": lon,
    }


def km_east(km, lat=FIELD[0], lon=FIELD[1]):
    """(lat, lon) `km` kilometres east of a point (flat projection used by the model)."""
    import math

    return lat, lon + km / (111.32 * math.cos(math.radians(lat)))


def km_north(km, lat=FIELD[0], lon=FIELD[1]):
    return lat + km / 111.32, lon


class FakeApi:
    """Stands in for LiveApi. Records calls; can be told to fail."""

    def __init__(
        self,
        wind=None,
        site_wind=None,
        places=None,
        fires=None,
        ensemble=None,
        fail_wind=False,
        fail_refine=False,
        fail_places=False,
        fail_fires=False,
        fires_key=True,
        places_delay=0.0,
        aq=None,
        met=None,
        stations=None,
        fail_air=False,
        fail_met=False,
        fail_stations=False,
    ):
        self.wind = wind or const_series(5, 270)
        self.site_wind = site_wind  # function(index, point) -> WindSeries for refine sites
        self._places = places or []
        self._fires = fires or []
        self._ensemble = ensemble
        self.fail_wind = fail_wind
        self.fail_refine = fail_refine
        self.fail_places = fail_places
        self.fail_fires = fail_fires
        self.fires_key = fires_key
        self.places_delay = places_delay
        self.aq = dict(AQ_DEFAULT, **(aq or {}))
        self.met_values = dict(MET_DEFAULT, **(met or {}))
        self._stations = stations
        self.fail_air = fail_air
        self.fail_met = fail_met
        self.fail_stations = fail_stations
        self.calls = []
        air.clear_cache()  # the module keeps CAMS for an hour; every test starts clean

    def forecast(self, points, days, level, past_days=0, timeout=None):
        self.calls.append(("forecast", list(points)))
        self.past_days = past_days
        if self.fail_wind:
            raise ApiError("Open-Meteo answered HTTP 500")
        if len(points) > 1 and self.fail_refine:
            raise ApiError("Open-Meteo did not answer within 8 s")
        out = []
        for i, pt in enumerate(points):
            if i > 0 and self.site_wind is not None:
                out.append(self.site_wind(i, pt))
            else:
                out.append(self.wind)
        return out

    def ensemble(self, lat, lon, days, past_days=0):
        self.calls.append(("ensemble",))
        if self._ensemble is None:
            raise ApiError("Open-Meteo ensemble answered HTTP 503")
        return self._ensemble

    def places(self, line, timeout):
        self.calls.append(("places", list(line)))
        if self.places_delay:
            import time

            time.sleep(self.places_delay)
        if self.fail_places:
            raise ApiError("OpenStreetMap (Overpass) answered HTTP 429")
        return list(self._places), None

    def fires_available(self):
        return self.fires_key

    def fires_box(self, source, box, days):
        self.calls.append(("fires_box", source))
        if self.fail_fires:
            raise ApiError(f"NASA FIRMS {source} answered HTTP 400: Invalid MAP_KEY.")
        return [dict(f, source=source) for f in self._fires if f.get("source", source) == source]

    def fires(self, source, lat, lon):
        self.calls.append(("fires", source))
        if self.fail_fires:
            raise ApiError(f"NASA FIRMS {source} answered HTTP 400: Invalid MAP_KEY.")
        return [dict(f, source=source) for f in self._fires]

    def count(self, kind):
        return sum(1 for c in self.calls if c[0] == kind)

    # ---- air quality ----------------------------------------------------------------
    def air_quality(self, spec, past_days, forecast_days):
        self.calls.append(("air_quality", dict(spec)))
        if self.fail_air:
            raise ApiError("Open-Meteo air quality answered HTTP 500")
        return const_grid(spec, self.aq)

    def met(self, spec, past_days, forecast_days):
        self.calls.append(("met", dict(spec)))
        if self.fail_met:
            raise ApiError("Open-Meteo weather answered HTTP 500")
        return const_grid(spec, self.met_values)

    def stations_available(self):
        return self._stations is not None

    def stations(self, bbox, now):
        self.calls.append(("stations", bbox))
        if self.fail_stations:
            raise ApiError("OpenAQ answered HTTP 401")
        return list(self._stations)


AQ_DEFAULT = {"pm2_5": 60.0, "pm10": 100.0, "co": 1000.0, "no2": 20.0, "so2": 10.0, "o3": 40.0}
MET_DEFAULT = {"mix": 500.0, "wind10": 3.0, "sun": 0.0, "cloud": 0.0}
GRID_T0 = DAY0 - timedelta(days=3)
GRID_HOURS = 6 * 24


def const_grid(spec, values, t0=GRID_T0, hours=GRID_HOURS):
    """A FieldGrid with the same value everywhere and at every hour."""
    n = spec["rows"] * spec["cols"]
    return FieldGrid(spec["south"], spec["west"], spec["step"], spec["rows"], spec["cols"], t0,
                     {k: [[float(v)] * hours for _ in range(n)] for k, v in values.items()})
