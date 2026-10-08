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
from pathlib import Path

from . import fires, places, wind
from .net import ApiError

FIRE_SOURCES = fires.SOURCES


class LiveApi:
    def __init__(self, firms_key=None):
        self.firms_key = firms_key

    @classmethod
    def from_env(cls):
        # API key consumed here: NASA FIRMS MAP_KEY from the FIRMS_MAP_KEY env var.
        return cls(firms_key=fires.map_key())

    # ---- raw replies -------------------------------------------------------
    def forecast_raw(self, points, days, level):
        return wind.fetch_forecast_raw(points, days, level)

    def ensemble_raw(self, lat, lon, days):
        return wind.fetch_ensemble_raw(lat, lon, days)

    def places_raw(self, line, timeout):
        return places.fetch_places_raw(line, timeout)

    def fires_raw(self, source, lat, lon):
        return fires.fetch_fires_raw(source, lat, lon, self.firms_key)

    def fires_available(self):
        return bool(self.firms_key)

    # ---- parsed results (shared by every flavour) --------------------------
    def forecast(self, points, days, level):
        """One WindSeries per point, in the same order. ONE request for all points."""
        series = wind.decode_forecast(self.forecast_raw(points, days, level), level)
        if len(series) != len(points):
            raise ApiError(f"Open-Meteo sent {len(series)} forecasts for {len(points)} points")
        return series

    def ensemble(self, lat, lon, days):
        return wind.decode_ensemble(self.ensemble_raw(lat, lon, days))

    def places(self, line, timeout):
        """(places, note or None)."""
        return places.decode_places(self.places_raw(line, timeout))

    def fires(self, source, lat, lon):
        text = self.fires_raw(source, lat, lon)
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


def firms_file(source):
    return f"firms_{source}.csv"


def raw_fixture_names():
    return [FORECAST_FIELD, FORECAST_MULTI, ENSEMBLE, OVERPASS] + [firms_file(s) for s in FIRE_SOURCES]


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

    def forecast_raw(self, points, days, level):
        body = super().forecast_raw(points, days, level)
        self._save(_forecast_file(points), body)
        return body

    def ensemble_raw(self, lat, lon, days):
        body = super().ensemble_raw(lat, lon, days)
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

    def forecast_raw(self, points, days, level):
        return self._load(_forecast_file(points))

    def ensemble_raw(self, lat, lon, days):
        return self._load(ENSEMBLE)

    def places_raw(self, line, timeout):
        return self._load(OVERPASS)

    def fires_raw(self, source, lat, lon):
        return self._load(firms_file(source)).decode("utf-8", errors="replace")

    def fires_available(self):
        return any((self.folder / firms_file(s)).exists() for s in FIRE_SOURCES)


def load_meta(folder):
    return json.loads((Path(folder) / META).read_text(encoding="utf-8"))
