"""Save real API replies into fixtures/ and rebuild the sample demo response.

    python3.12 scripts/save_fixtures.py
        Demo field 30.245, 75.844 (Sangrur, Punjab), burn tomorrow 2 pm, 24 hours.
    python3.12 scripts/save_fixtures.py 30.245 75.844 2026-10-10T14:00 24
    python3.12 scripts/save_fixtures.py --offline
        No network: only rebuild the sample from replies already in fixtures/.

Set FIRMS_MAP_KEY in your shell first so the sample includes real fires.

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

from smoke_path import IST  # noqa: E402
from smoke_path.apis import (  # noqa: E402
    ENSEMBLE,
    META,
    OVERPASS,
    SAMPLE,
    FixtureApi,
    RecordingApi,
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
PACKAGE_SAMPLE = ROOT / "src" / "smoke_path" / SAMPLE
MAP_HTML = ROOT / "frontend" / "map.html"
DEMO_FIELD = ("30.245", "75.844")

SAMPLE_BLOCK = re.compile(
    r'(<script id="sample-data" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)


def json_for_html(doc):
    """JSON that is safe inside a <script> block (no '<', '>' or '&' characters)."""
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def embed_sample(html, doc):
    """Put `doc` inside the sample-data block of map.html."""
    if not SAMPLE_BLOCK.search(html):
        raise SystemExit('map.html has no <script id="sample-data" type="application/json"> block')
    payload = json_for_html(doc)
    return SAMPLE_BLOCK.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)


def embedded_sample(html):
    """The sample currently embedded in map.html (or None)."""
    m = SAMPLE_BLOCK.search(html)
    return json.loads(m.group(2)) if m else None


def places_complete():
    """True if fixtures/overpass.json exists and is a complete (not cut short) answer."""
    path = FIXTURES / OVERPASS
    if not path.exists():
        return False
    try:
        _, note = decode_places(path.read_bytes())
    except ApiError:
        return False
    return note is None


def retry_places(doc, api, retries, wait_s=20):
    """Overpass is often busy. Retry just the places call a few times (saved by RecordingApi)."""
    path = next(f for f in doc["features"] if f["properties"]["kind"] == "path")
    line = [(lat, lon) for lon, lat in path["geometry"]["coordinates"][::4]]  # hourly points
    for attempt in range(1, retries + 1):
        print(f"Places missing or incomplete; retrying OpenStreetMap in {wait_s} s (attempt {attempt}/{retries}) ...")
        time.sleep(wait_s)
        try:
            api.places_raw(line, 120)
        except ApiError as err:
            print(f"  still failing: {err}")
            continue
        if places_complete():
            print("  OpenStreetMap answered with a complete list.")
            return True
        print("  OpenStreetMap answered, but the search was cut short.")
    return False


def record(req, places_retries=2):
    """Call the live APIs once (ensemble mode, so every API is used) and save raw replies."""
    FIXTURES.mkdir(exist_ok=True)
    for name in raw_fixture_names():  # remove stale replies from an older run
        (FIXTURES / name).unlink(missing_ok=True)
    key = map_key()
    print(f"FIRMS key: {'set' if key else 'NOT set - fires will be missing from the sample'}")
    api = RecordingApi(FIXTURES, firms_key=key)
    live_req = SmokeRequest(req.lat, req.lon, req.start, req.hours, "ensemble")
    # Not behind API Gateway, so wait longer for a busy Overpass server.
    result = run(live_req, api, budget_s=150, places_timeout_s=120)
    if not places_complete() and places_retries:
        retry_places(result.report, api, places_retries)
    if not places_complete():
        print("WARNING: no complete list of places was saved. Run this script again later.")
    meta = {
        "lat": req.lat,
        "lon": req.lon,
        "start": req.start.isoformat(timespec="minutes"),
        "hours": req.hours,
        "wind_level": wind_level(),
        "saved_at": datetime.now(IST).isoformat(timespec="seconds"),
        "live_notes": result.report["notes"],
    }
    (FIXTURES / META).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\nSaved replies:")
    for name in raw_fixture_names():
        path = FIXTURES / name
        print(f"  {'OK     ' if path.exists() else 'MISSING'} fixtures/{name}" + (f"  ({path.stat().st_size:,} bytes)" if path.exists() else ""))
    if result.report["notes"]:
        print("\nNotes from the live run:")
        for note in result.report["notes"]:
            print("  - " + note)
    describe_ensemble_keys()


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
    parser.add_argument("--places-retries", type=int, default=2, help="extra tries if OpenStreetMap is busy (default 2)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if not args.offline:
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
