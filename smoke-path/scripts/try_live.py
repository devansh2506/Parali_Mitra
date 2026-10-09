"""Call the real APIs once, print the summary and notes, and save smoke.geojson.

    python3.12 scripts/try_live.py LAT LON [START] [HOURS] [--ensemble]

    python3.12 scripts/try_live.py 30.245 75.844
    python3.12 scripts/try_live.py 30.245 75.844 2026-10-10T14:00 24
    python3.12 scripts/try_live.py 30.245 75.844 2026-10-10T14:00 48 --ensemble
    python3.12 scripts/try_live.py 30.60486 74.99966 2026-10-09T12:37 24 --fire

--fire traces smoke from a fire already seen by satellite (START = the time it was seen,
up to 3 days ago), instead of a planned burn on your field.

START is India time (YYYY-MM-DDTHH:MM); default is the next full hour.
Fires use FIRMS_MAP_KEY from smoke-path/.env (or your shell).
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _env import load_env  # noqa: E402

from smoke_path.apis import LiveApi  # noqa: E402
from smoke_path.app import BadRequest, parse_request  # noqa: E402
from smoke_path.pipeline import WindUnavailable, run  # noqa: E402
from smoke_path.wind import OutsideForecast  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lat")
    parser.add_argument("lon")
    parser.add_argument("start", nargs="?", default="")
    parser.add_argument("hours", nargs="?", default="")
    parser.add_argument("--ensemble", action="store_true", help="use the ICON-EPS ensemble band")
    parser.add_argument("--fire", action="store_true", help="START is when a satellite saw a fire here")
    parser.add_argument("--out", default="smoke.geojson", help="output file (default: smoke.geojson)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    load_env()  # FIRMS_MAP_KEY etc. from smoke-path/.env (shell variables win)

    params = {
        "lat": args.lat,
        "lon": args.lon,
        "start": args.start,
        "hours": args.hours,
        "uncertainty": "ensemble" if args.ensemble else "cone",
        "origin": "fire" if args.fire else "field",
    }
    try:
        req = parse_request(params)
    except BadRequest as err:
        print(f"Bad input: {err}")
        return 2

    api = LiveApi.from_env()
    what = "fire seen" if req.origin == "fire" else "burn"
    print(f"{req.origin.title()} {req.lat}, {req.lon} | {what} {req.start:%Y-%m-%d %H:%M} IST | {req.hours} h | band: {req.uncertainty}")
    print(f"FIRMS key: {'set' if api.fires_available() else 'NOT set (fires will be skipped)'}")
    t0 = time.monotonic()
    try:
        result = run(req, api)
    except OutsideForecast as err:
        print(f"400: {err}")
        return 2
    except WindUnavailable as err:
        print(f"502: Wind forecast unavailable: {err}")
        return 3
    took = time.monotonic() - t0

    doc = result.report
    feats = doc["features"]

    def kind(k):
        return [f["properties"] for f in feats if f["properties"]["kind"] == k]

    places = kind("place")
    in_band = [p for p in places if p["in_band"]]
    print()
    print(doc["label"].upper())
    for line in doc["summary"]:
        print("  " + line)
    print()
    print("Notes:" if doc["notes"] else "Notes: none")
    for note in doc["notes"]:
        print("  - " + note)
    print()
    print(f"Path length:   {kind('path')[0]['km']} km over {doc['hours']} h (wind at {doc['wind_level']})")
    print(f"Band:          {doc['uncertainty']}, {len(kind('puff'))} puffs, last radius {kind('puff')[-1]['radius_km']} km")
    if doc["uncertainty"] == "ensemble":
        print(f"Members:       {len(kind('member'))}")
    print(f"Places:        {len(places)} found, {len(in_band)} in the band")
    for p in in_band[:10]:
        print(f"   {p['arrival_text']:>18}  {p['name']} ({p['place_type']}), {p['distance_km']} km from path")
    print(f"Fires:         {len(kind('fire'))}")
    print(f"Took:          {took:.1f} s (must stay under ~25 s for API Gateway)")

    out = Path(args.out)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved {out.resolve()}  (open it at https://geojson.io to look at it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
