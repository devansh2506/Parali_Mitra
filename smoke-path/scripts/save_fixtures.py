"""Save real API replies into fixtures/ and rebuild the sample demo response.

    python3.12 scripts/save_fixtures.py
        Demo field 30.245, 75.844 (Sangrur, Punjab), burn tomorrow 2 pm, 24 hours.
    python3.12 scripts/save_fixtures.py 30.245 75.844 2026-10-10T14:00 24
    python3.12 scripts/save_fixtures.py --fires-only
        Refresh only today's fires (keeps the saved path and places), then rebuild.
    python3.12 scripts/save_fixtures.py --offline
        No network: only rebuild the sample from replies already in fixtures/.

Fires use FIRMS_MAP_KEY from smoke-path/.env (or your shell).

A new capture never makes the sample worse: if OpenStreetMap is busy and the
new list of places is incomplete, the previous wind + places are kept (they
belong together) and only the fires are updated.

Writes:
  fixtures/forecast_field.json   Open-Meteo, wind at the field (pass 1)
  fixtures/forecast_multi.json   Open-Meteo, field + points along the path (pass 2)
  fixtures/ensemble.json         Open-Meteo ensemble (ICON-EPS)
  fixtures/overpass.json         OpenStreetMap places along the path
  fixtures/firms_<SOURCE>.csv    NASA FIRMS fires (only with FIRMS_MAP_KEY)
  fixtures/meta.json             what was requested, and when
  fixtures/sample_response.json  the demo response returned for sample=true
  src/smoke_path/sample_response.json   same file, packaged with the Lambda
  frontend/map.html              sample embedded so the page works without an API
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _env import load_env  # noqa: E402

from smoke_path import IST, airquality  # noqa: E402
from smoke_path.apis import (  # noqa: E402
    AIR_QUALITY,
    ENSEMBLE,
    FIRE_SOURCES,
    MET,
    META,
    OVERPASS,
    SAMPLE,
    FixtureApi,
    LiveApi,
    RecordingApi,
    firms_file,
    load_meta,
    raw_fixture_names,
)
from smoke_path.app import BadRequest, parse_request  # noqa: E402
from smoke_path.fires import map_key  # noqa: E402
from smoke_path.net import ApiError  # noqa: E402
from smoke_path.places import decode_places  # noqa: E402
from smoke_path.pipeline import SmokeRequest, WindUnavailable, run  # noqa: E402
from smoke_path.wind import OutsideForecast, wind_level  # noqa: E402

FIXTURES = ROOT / "fixtures"
NEW_CAPTURE = FIXTURES / "_new"  # a capture is recorded here first, then adopted
PACKAGE_SAMPLE = ROOT / "src" / "smoke_path" / SAMPLE
MAP_HTML = ROOT / "frontend" / "map.html"
DEMO_FIELD = ("30.245", "75.844")

def _block(block_id):
    return re.compile(r'(<script id="' + block_id + r'" type="application/json">)(.*?)(</script>)', re.DOTALL)


SAMPLE_BLOCK = _block("sample-data")  # the "What if I burn?" sample
FIRE_WATCH_BLOCK = "fire-watch-sample"  # the fire watch sample


def json_for_html(doc):
    """JSON that is safe inside a <script> block (no '<', '>' or '&' characters)."""
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def embed_sample(html, doc, block_id="sample-data"):
    """Put `doc` inside a sample block of map.html."""
    pattern = _block(block_id)
    if not pattern.search(html):
        raise SystemExit(f'map.html has no <script id="{block_id}" type="application/json"> block')
    payload = json_for_html(doc)
    return pattern.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)


def embedded_sample(html, block_id="sample-data"):
    """The sample currently embedded in map.html (or None)."""
    m = _block(block_id).search(html)
    return json.loads(m.group(2)) if m else None


def places_complete(folder=FIXTURES):
    """True if <folder>/overpass.json exists and is a complete (not cut short) answer."""
    path = Path(folder) / OVERPASS
    if not path.exists():
        return False
    try:
        _, note = decode_places(path.read_bytes())
    except ApiError:
        return False
    return note is None


def retry_places(doc, api, retries, wait_s=20):
    """Overpass is often busy. Retry just the places lookup a few times (live replies are saved)."""
    path = next(f for f in doc["features"] if f["properties"]["kind"] == "path")
    line = [(lat, lon) for lon, lat in path["geometry"]["coordinates"][::4]]  # hourly points
    for attempt in range(1, retries + 1):
        print(f"Places missing or incomplete; retrying OpenStreetMap in {wait_s} s (attempt {attempt}/{retries}) ...")
        time.sleep(wait_s)
        try:
            _, note = api.places(line, 120)
        except ApiError as err:
            print(f"  still failing: {err}")
            continue
        if note is None:
            print("  Places complete.")
            return True
        print(f"  still incomplete: {note}")
    return False


def _write_meta(folder, meta):
    (Path(folder) / META).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def adopt(new_dir, fixtures_dir, meta):
    """Move a new capture into fixtures/ without ever making the sample worse.

    Returns "all" (new capture adopted) or "fires_only" (new places were
    incomplete, so the previous wind + places were kept and only fires moved).
    """
    new_dir, fixtures_dir = Path(new_dir), Path(fixtures_dir)
    old_meta = load_meta(fixtures_dir) if (fixtures_dir / META).exists() else None
    old_ok = bool(old_meta) and old_meta.get("places_checked", places_complete(fixtures_dir))
    if not meta.get("places_checked", places_complete(new_dir)) and old_ok:
        moved = False
        for source in FIRE_SOURCES:  # fires do not depend on the path, so they can be swapped in
            src = new_dir / firms_file(source)
            if src.exists():
                src.replace(fixtures_dir / firms_file(source))
                moved = True
        if moved:
            old_meta["fires_saved_at"] = meta["saved_at"]
            _write_meta(fixtures_dir, old_meta)
        return "fires_only"
    for name in raw_fixture_names():
        (fixtures_dir / name).unlink(missing_ok=True)
        src = new_dir / name
        if src.exists():
            src.replace(fixtures_dir / name)
    _write_meta(fixtures_dir, meta)
    return "all"


def _remove_capture_dir(folder):
    if folder.exists():
        for path in folder.iterdir():
            path.unlink()
        folder.rmdir()


def record(req, places_retries=2):
    """Call the live APIs once (ensemble mode, so every API is used) and save raw replies."""
    FIXTURES.mkdir(exist_ok=True)
    _remove_capture_dir(NEW_CAPTURE)
    NEW_CAPTURE.mkdir()
    key = map_key()
    print(f"FIRMS key: {'set' if key else 'NOT set - fires will be missing from the sample'}")
    try:
        api = RecordingApi(NEW_CAPTURE, firms_key=key)
        live_req = SmokeRequest(req.lat, req.lon, req.start, req.hours, "ensemble")
        # Not behind API Gateway, so wait longer for a busy Overpass server.
        result = run(live_req, api, budget_s=150, places_timeout_s=120)
        places_ok = result.places_checked
        if not places_ok and places_retries:
            places_ok = retry_places(result.report, api, places_retries)
        meta = {
            "lat": req.lat,
            "lon": req.lon,
            "start": req.start.isoformat(timespec="minutes"),
            "hours": req.hours,
            "wind_level": wind_level(),
            "saved_at": datetime.now(IST).isoformat(timespec="seconds"),
            "live_notes": result.report["notes"],
            "places_checked": places_ok,
        }
        adopted = adopt(NEW_CAPTURE, FIXTURES, meta)
    finally:
        _remove_capture_dir(NEW_CAPTURE)

    if adopted == "fires_only":
        print("\nOpenStreetMap was busy, so the new list of places was incomplete.")
        print("Kept the previous wind + places (they belong together) and updated only the fires.")
        print("Run this script again later for a completely new capture.")
    elif not places_ok:
        print("\nWARNING: no complete list of places was saved. Run this script again later.")
    print("\nSaved replies:")
    for name in raw_fixture_names():
        path = FIXTURES / name
        print(f"  {'OK     ' if path.exists() else 'MISSING'} fixtures/{name}" + (f"  ({path.stat().st_size:,} bytes)" if path.exists() else ""))
    if result.report["notes"]:
        print("\nNotes from the live run:")
        for note in result.report["notes"]:
            print("  - " + note)
    describe_ensemble_keys()


def refresh_fires():
    """Re-download only the FIRMS fires for the saved field. Returns True if any source worked."""
    meta = load_meta(FIXTURES)
    key = map_key()
    if not key:
        print("FIRMS_MAP_KEY is not set in this terminal.")
        return False
    api = RecordingApi(FIXTURES, firms_key=key)  # saves only on success, so old files stay on failure
    worked = 0
    for source in FIRE_SOURCES:
        try:
            text = api.fires_raw(source, float(meta["lat"]), float(meta["lon"]))
        except ApiError as err:
            print(f"  FAILED {source}: {err}")
            continue
        worked += 1
        print(f"  OK     {source}: {max(0, len(text.strip().splitlines()) - 1)} fires")
    if worked:
        meta["fires_saved_at"] = datetime.now(IST).isoformat(timespec="seconds")
        fire_notes = ("Fires unavailable", "Some satellite fire data")
        meta["live_notes"] = [n for n in meta.get("live_notes", []) if not n.startswith(fire_notes)]
        _write_meta(FIXTURES, meta)
    return worked > 0


def refresh_air():
    """Download only the air-quality and weather grids for the saved burn (wind, places, fires kept)."""
    meta = load_meta(FIXTURES)
    start = datetime.fromisoformat(meta["start"]).astimezone(IST)
    req = SmokeRequest(float(meta["lat"]), float(meta["lon"]), start, int(meta["hours"]), "cone")
    saved_at = datetime.fromisoformat(meta["saved_at"]).astimezone(IST)

    class AirRecording(FixtureApi):
        """Saved wind, places and fires; live CAMS and weather, saved as they arrive."""

        def air_quality(self, spec, past_days, forecast_days):
            grid = LiveApi.air_quality(self, spec, past_days, forecast_days)
            (FIXTURES / AIR_QUALITY).write_text(json.dumps(airquality.grid_to_json(grid), separators=(",", ":")))
            return grid

        def met(self, spec, past_days, forecast_days):
            grid = LiveApi.met(self, spec, past_days, forecast_days)
            (FIXTURES / MET).write_text(json.dumps(airquality.grid_to_json(grid), separators=(",", ":")))
            return grid

    result = run(req, AirRecording(FIXTURES), level=meta.get("wind_level"), now=saved_at)
    ok = (FIXTURES / AIR_QUALITY).exists() and (FIXTURES / MET).exists()
    print("  air quality and weather saved" if ok else "  FAILED: " + "; ".join(result.report["notes"]))
    return ok


def describe_ensemble_keys():
    """Print the real member key format, so we can confirm the parser's grouping."""
    path = FIXTURES / ENSEMBLE
    if not path.exists():
        return
    hourly = json.loads(path.read_text(encoding="utf-8")).get("hourly", {})
    speed = sorted(k for k in hourly if k.startswith("wind_speed_10m"))
    direction = sorted(k for k in hourly if k.startswith("wind_direction_10m"))
    print(f"\nEnsemble keys: {len(speed)} speed keys ({speed[0]} ... {speed[-1]}), {len(direction)} direction keys")


def build_sample():
    """Rebuild the demo response from saved replies only (no network)."""
    meta = load_meta(FIXTURES)
    start = datetime.fromisoformat(meta["start"]).astimezone(IST)
    req = SmokeRequest(float(meta["lat"]), float(meta["lon"]), start, int(meta["hours"]), "cone")
    saved_at = datetime.fromisoformat(meta["saved_at"]).astimezone(IST)
    result = run(req, FixtureApi(FIXTURES), level=meta.get("wind_level"), now=saved_at)
    doc = result.report
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    (FIXTURES / SAMPLE).write_text(text, encoding="utf-8")
    PACKAGE_SAMPLE.write_text(text, encoding="utf-8")
    MAP_HTML.write_text(embed_sample(MAP_HTML.read_text(encoding="utf-8"), doc), encoding="utf-8")

    print("\nSample demo response:")
    for line in doc["summary"]:
        print("  " + line)
    for note in doc["notes"]:
        print("  note: " + note)
    kinds = {}
    for f in doc["features"]:
        kinds[f["properties"]["kind"]] = kinds.get(f["properties"]["kind"], 0) + 1
    print(f"  features: {kinds}")
    print(f"\nWrote fixtures/{SAMPLE}, src/smoke_path/{SAMPLE} and the sample inside frontend/map.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lat", nargs="?", default=DEMO_FIELD[0])
    parser.add_argument("lon", nargs="?", default=DEMO_FIELD[1])
    parser.add_argument("start", nargs="?", default="", help="India time YYYY-MM-DDTHH:MM (default: tomorrow 14:00)")
    parser.add_argument("hours", nargs="?", default="24")
    parser.add_argument("--offline", action="store_true", help="only rebuild the sample from saved replies")
    parser.add_argument("--fires-only", action="store_true", help="refresh only today's fires, keep path and places")
    parser.add_argument("--places-retries", type=int, default=2, help="extra tries if OpenStreetMap is busy (default 2)")
    parser.add_argument("--air-only", action="store_true", help="refresh only the air-quality data, keep the rest")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    load_env()  # FIRMS_MAP_KEY etc. from smoke-path/.env (shell variables win)

    if args.air_only:
        if not (FIXTURES / META).exists():
            print("No fixtures/meta.json yet. Run this script once without --air-only.")
            return 2
        print("Refreshing the air-quality forecast for the saved burn ...")
        if not refresh_air():
            print("Air quality was not updated.")
    elif args.fires_only:
        if not (FIXTURES / META).exists():
            print("No fixtures/meta.json yet. Run this script once without --fires-only.")
            return 2
        print("Refreshing today's fires for the saved field ...")
        if not refresh_fires():
            print("Fires were not updated; the sample keeps the previous fires.")
    elif not args.offline:
        start = args.start
        if not start:
            tomorrow = datetime.now(IST).date() + timedelta(days=1)
            start = f"{tomorrow.isoformat()}T14:00"
        try:
            req = parse_request({"lat": args.lat, "lon": args.lon, "start": start, "hours": args.hours})
        except BadRequest as err:
            print(f"Bad input: {err}")
            return 2
        print(f"Recording live replies for {req.lat}, {req.lon}, burn {start} IST, {req.hours} h ...")
        try:
            record(req, args.places_retries)
        except (OutsideForecast, WindUnavailable) as err:
            print(f"Could not get the wind forecast: {err}")
            return 3

    if not (FIXTURES / META).exists():
        print("No fixtures/meta.json yet. Run this script once without --offline.")
        return 2
    build_sample()
    return 0


if __name__ == "__main__":
    sys.exit(main())
