"""Save the data the web app shows when there is no server (and for the recorded demo), as plain script files.

    python3.12 scripts/save_frontend_samples.py             # fetch stations and the forecast live, reuse the saved fire sample
    python3.12 scripts/save_frontend_samples.py --offline   # rebuild the script files from fixtures/ only (no network)

Fires:     fixtures/fire_watch_sample.json (made by scripts/save_fire_watch_sample.py). Each fire gets its stable key and
           its state here, so an older sample works too.
Stations:  fixtures/stations_sample.json   (live: OpenAQ)
Forecast:  fixtures/forecast_sample.json   (live: CAMS through Open-Meteo, ~484 location calls)

Writes frontend/data/sample-fires.js and frontend/data/sample-air.js. They are scripts, not JSON, because a page
opened straight from disk (file://) cannot fetch() files. If a live call fails, the saved fixture is kept.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _env import load_env  # noqa: E402

from smoke_path import IST, air, region, station_air  # noqa: E402
from smoke_path.firewatch import fire_key  # noqa: E402
from smoke_path.apis import LiveApi  # noqa: E402

FIX = ROOT / "fixtures"
OUT = ROOT / "frontend" / "data"


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def enrich_fires(doc):
    """Add key and state to each fire; drop the per-detection list (the app does not use it)."""
    n, used = 0, set()
    for f in doc["features"]:
        p = f["properties"]
        if p.get("kind") != "fire":
            continue
        lon, lat = f["geometry"]["coordinates"]
        if not p.get("key"):
            p["key"] = fire_key(lat, lon, p["seen_at"], used)
        used.add(p["key"])
        if not p.get("state"):
            p["state"] = region.state_of(lat, lon)
        p.pop("details", None)
        n += 1
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    offline = "--offline" in argv
    load_env()
    now = datetime.now(IST)
    fires = json.loads((FIX / "fire_watch_sample.json").read_text(encoding="utf-8"))
    n = enrich_fires(fires)
    fires["sample"] = True
    print(f"fires: {n} (sample from {fires['generated_at']})")

    stations_path, forecast_path = FIX / "stations_sample.json", FIX / "forecast_sample.json"
    if not offline:
        try:
            doc, _ = station_air.live(now)
            stations_path.write_text(dump(doc), encoding="utf-8")
            print(f"stations: {len(doc['stations'])} from {doc['source']}")
        except Exception as err:  # noqa: BLE001 - keep the saved file
            print(f"stations: live fetch failed ({err}); keeping the saved sample")
        try:
            grid = air.forecast_grid(LiveApi.from_env(), now)
            doc = dict(air.overlay(grid, now), source="CAMS global forecast (ECMWF), via Open-Meteo", generated_at=now.isoformat(timespec="minutes"))
            forecast_path.write_text(dump(doc), encoding="utf-8")
            print(f"forecast: {len(doc['times'])} times on {doc['rows']}x{doc['cols']} points")
        except Exception as err:  # noqa: BLE001
            print(f"forecast: live fetch failed ({err}); keeping the saved sample")
    for path in (stations_path, forecast_path):
        if not path.exists():
            raise SystemExit(f"{path.name} is missing: run once without --offline")
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    forecast = json.loads(forecast_path.read_text(encoding="utf-8"))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample-fires.js").write_text("window.PM_SAMPLE = window.PM_SAMPLE || {};\nwindow.PM_SAMPLE.fires = " + dump(fires) + ";\n", encoding="utf-8")
    (OUT / "sample-air.js").write_text(
        "window.PM_SAMPLE = window.PM_SAMPLE || {};\nwindow.PM_SAMPLE.stations = " + dump(stations) + ";\nwindow.PM_SAMPLE.forecast = " + dump(forecast) + ";\n", encoding="utf-8")
    for name in ("sample-fires.js", "sample-air.js"):
        print(f"wrote frontend/data/{name} ({(OUT / name).stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
