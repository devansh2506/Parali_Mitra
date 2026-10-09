"""Access to the four external APIs, in three flavours.

* LiveApi      calls the real services (used by Lambda and scripts/try_live.py).
* RecordingApi calls the real services and saves every raw reply to a folder
               (used by scripts/save_fixtures.py).
* FixtureApi   reads those saved replies, with no network at all (used to build
               the sample demo response, and in tests).

Each flavour only changes the "raw" methods; parsing is shared, so saved
replies go through exactly the same code as live ones.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import airquality, fires, places, snapshot, stations, wind
from .net import ApiError

FIRE_SOURCES = fires.SOURCES


class LiveApi:
    def __init__(self, firms_key=None, openaq_key=None):
        self.firms_key = firms_key
        self.openaq_key = openaq_key

    @classmethod
    def from_env(cls):
        # API keys consumed here: NASA FIRMS MAP_KEY (FIRMS_MAP_KEY) and OpenAQ (OPENAQ_API_KEY).
        return cls(firms_key=fires.map_key(), openaq_key=stations.api_key())

    # ---- raw replies -------------------------------------------------------
    def forecast_raw(self, points, days, level, past_days=0, timeout=None):
        return wind.fetch_forecast_raw(
            points, days, level, timeout=timeout or wind.FORECAST_TIMEOUT_S, past_days=past_days
        )

    def ensemble_raw(self, lat, lon, days, past_days=0):
        return wind.fetch_ensemble_raw(lat, lon, days, past_days=past_days)

    def places_raw(self, line, timeout):
        return places.fetch_places_raw(line, timeout)

    def fires_raw(self, source, lat, lon):
        return fires.fetch_fires_raw(source, lat, lon, self.firms_key)

    def fires_box_raw(self, source, box, days):
        return fires.fetch_fires_box_raw(source, box, self.firms_key, days)

    def fires_available(self):
        return bool(self.firms_key)

    def air_quality_raw(self, points, past_days, forecast_days):
        return airquality.fetch_aq_raw(points, past_days, forecast_days)

    def met_raw(self, points, past_days, forecast_days):
        return airquality.fetch_met_raw(points, past_days, forecast_days)

    def stations_available(self):
        return bool(self.openaq_key)

    def stations(self, bbox, now):
        """Latest station readings in bbox (south, west, north, east)."""
        return stations.fetch_stations(bbox, self.openaq_key, now)

    # ---- parsed results (shared by every flavour) --------------------------
    def forecast(self, points, days, level, past_days=0, timeout=None):
        """One WindSeries per point, in the same order. ONE request for all points."""
        series = wind.decode_forecast(self.forecast_raw(points, days, level, past_days, timeout), level)
        if len(series) != len(points):
            raise ApiError(f"Open-Meteo sent {len(series)} forecasts for {len(points)} points")
        return series

    def ensemble(self, lat, lon, days, past_days=0):
        return wind.decode_ensemble(self.ensemble_raw(lat, lon, days, past_days))

    def places(self, line, timeout):
        """(places, note or None): saved snapshot first, live Overpass only outside it."""
        return places.find_places(line, timeout, self.places_raw, snapshot.get())

    def fires(self, source, lat, lon):
        text = self.fires_raw(source, lat, lon)
        if not fires.looks_like_firms_csv(text):
            raise ApiError(f"NASA FIRMS {source} did not send fire data")
        return fires.parse_fires_csv(text, source)

    def air_quality(self, spec, past_days, forecast_days):
        """CAMS forecast on a grid (airquality.grid_spec) as a FieldGrid, in as few requests as fit."""
        chunks = airquality.chunks(airquality.FieldGrid.points(**spec))
        with ThreadPoolExecutor(max_workers=min(8, len(chunks))) as pool:
            raws = list(pool.map(lambda c: self.air_quality_raw(c, past_days, forecast_days), chunks))
        return airquality.decode_grid(raws, spec)

    def met(self, spec, past_days, forecast_days):
        """Mixing height, 10 m wind, sunshine and cloud on the same grid, as a FieldGrid."""
        chunks = airquality.chunks(airquality.FieldGrid.points(**spec))
        with ThreadPoolExecutor(max_workers=min(8, len(chunks))) as pool:
            raws = list(pool.map(lambda c: self.met_raw(c, past_days, forecast_days), chunks))
        return airquality.decode_met(raws, spec)

    def fires_box(self, source, box, days):
        """Every detection from one satellite source in a region box (fire watch)."""
        text = self.fires_box_raw(source, box, days)
        if not fires.looks_like_firms_csv(text):
            raise ApiError(f"NASA FIRMS {source} did not send fire data")
        return fires.parse_fires_csv(text, source)


# File names used for saved replies.
FORECAST_FIELD = "forecast_field.json"  # pass 1: wind at the field only
FORECAST_MULTI = "forecast_multi.json"  # pass 2: field + points along the path
ENSEMBLE = "ensemble.json"
OVERPASS = "overpass.json"
META = "meta.json"
SAMPLE = "sample_response.json"
AIR_QUALITY = "air_quality.json"  # CAMS on the grid around the burn sample's path (decoded grid)
MET = "met.json"  # mixing height etc. on the same grid (decoded grid)


def firms_file(source):
    return f"firms_{source}.csv"


def raw_fixture_names():
    return [FORECAST_FIELD, FORECAST_MULTI, ENSEMBLE, OVERPASS, AIR_QUALITY, MET] + [firms_file(s) for s in FIRE_SOURCES]


def _forecast_file(points):
    return FORECAST_FIELD if len(points) == 1 else FORECAST_MULTI


class RecordingApi(LiveApi):
    """Live calls that also save each raw reply into `folder`."""

    def __init__(self, folder, firms_key=None):
        super().__init__(firms_key)
        self.folder = Path(folder)

    def _save(self, name, data):
        path = self.folder / name
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)

    def forecast_raw(self, points, days, level, past_days=0, timeout=None):
        body = super().forecast_raw(points, days, level, past_days, timeout)
        self._save(_forecast_file(points), body)
        return body

    def ensemble_raw(self, lat, lon, days, past_days=0):
        body = super().ensemble_raw(lat, lon, days, past_days)
        self._save(ENSEMBLE, body)
        return body

    def places_raw(self, line, timeout):
        body = super().places_raw(line, timeout)
        self._save(OVERPASS, body)
        return body

    def fires_raw(self, source, lat, lon):
        text = super().fires_raw(source, lat, lon)
        self._save(firms_file(source), text)
        return text

    def air_quality(self, spec, past_days, forecast_days):
        grid = super().air_quality(spec, past_days, forecast_days)  # several requests: save the merged grid
        self._save(AIR_QUALITY, json.dumps(airquality.grid_to_json(grid), separators=(",", ":")))
        return grid

    def met(self, spec, past_days, forecast_days):
        grid = super().met(spec, past_days, forecast_days)
        self._save(MET, json.dumps(airquality.grid_to_json(grid), separators=(",", ":")))
        return grid

    def stations_available(self):
        return False  # station readings are not saved with the fixtures


class FixtureApi(LiveApi):
    """Replays replies saved by RecordingApi. No network."""

    def __init__(self, folder):
        super().__init__(firms_key=None)
        self.folder = Path(folder)

    def _load(self, name):
        path = self.folder / name
        if not path.exists():
            raise ApiError(f"No saved reply {name} in {self.folder.name}/")
        return path.read_bytes()

    def forecast_raw(self, points, days, level, past_days=0, timeout=None):
        return self._load(_forecast_file(points))

    def ensemble_raw(self, lat, lon, days, past_days=0):
        return self._load(ENSEMBLE)

    def places_raw(self, line, timeout):
        return self._load(OVERPASS)

    def fires_raw(self, source, lat, lon):
        return self._load(firms_file(source)).decode("utf-8", errors="replace")

    def fires_available(self):
        return any((self.folder / firms_file(s)).exists() for s in FIRE_SOURCES)

    def air_quality(self, spec, past_days, forecast_days):
        return airquality.grid_from_json(json.loads(self._load(AIR_QUALITY)))

    def met(self, spec, past_days, forecast_days):
        return airquality.grid_from_json(json.loads(self._load(MET)))

    def stations_available(self):
        return False


def load_meta(folder):
    return json.loads((Path(folder) / META).read_text(encoding="utf-8"))
