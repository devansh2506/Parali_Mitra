"""Download every city and town in India from OpenStreetMap once, so smoke paths outside
Punjab and Haryana can still say which towns they reach.

    python3.12 scripts/build_towns.py

(Villages, schools and hospitals for all of India are far too many for a free service and
a Lambda file, so they stay in places_snapshot.json.gz for Punjab, Haryana and nearby.)

Asks Overpass for the fire box in 4 x 4 parts, keeps each finished part in
.build_cache/towns/ (run again to continue after a failure) and writes
src/smoke_path/data/towns_india.json.gz in the same format as the places snapshot.

Data © OpenStreetMap contributors, ODbL 1.0.
"""

import gzip
import json
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_places_snapshot import TILE_DEG, WAITS_S, wait_for_slot  # noqa: E402

from smoke_path import IST  # noqa: E402
from smoke_path.firewatch import FIRE_BOX  # noqa: E402
from smoke_path.net import ApiError, parse_json, request  # noqa: E402
from smoke_path.places import _cut_short, overpass_url, parse_overpass  # noqa: E402
from smoke_path.snapshot import FORMAT  # noqa: E402

OUT = ROOT / "src" / "smoke_path" / "data" / "towns_india.json.gz"
CACHE = ROOT / ".build_cache" / "towns"
PARTS = 4


def parts():
    s, w, n, e = FIRE_BOX
    dl, dw = (n - s) / PARTS, (e - w) / PARTS
    return [(round(s + a * dl, 3), round(w + b * dw, 3), round(s + (a + 1) * dl, 3), round(w + (b + 1) * dw, 3))
            for a in range(PARTS) for b in range(PARTS)]


def fetch(box):
    q = (f"[out:json][timeout:120][maxsize:134217728][bbox:{box[0]},{box[1]},{box[2]},{box[3]}];\n"
         '(\n  node["place"~"^(city|town)$"];\n);\nout center tags;')
    raw = request(overpass_url(), 150, data=urllib.parse.urlencode({"data": q}).encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"}, name="OpenStreetMap (Overpass)")
    data = parse_json(raw, "OpenStreetMap (Overpass)")
    if _cut_short(data) or not isinstance(data.get("elements"), list):
        raise ApiError(f"cut short: {data.get('remark', 'no elements list')}")
    return raw


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    by_osm, stamps = {}, []
    todo = parts()
    for n, box in enumerate(todo, 1):
        path = CACHE / ("part_" + "_".join(str(x) for x in box) + ".json")
        if not path.exists():
            for wait in (0,) + WAITS_S:
                if wait:
                    print(f"    busy, waiting {wait} s ...", flush=True)
                    time.sleep(wait)
                wait_for_slot()
                try:
                    raw = fetch(box)
                except (ApiError, ValueError) as err:
                    print(f"  part {n}: {err}", flush=True)
                    continue
                path.write_bytes(raw)
                break
            else:
                raise SystemExit(f"part {n} kept failing; run again later to continue")
        data = json.loads(path.read_bytes())
        stamp = (data.get("osm3s") or {}).get("timestamp_osm_base")
        if stamp:
            stamps.append(stamp)
        for p in parse_overpass(data):
            by_osm.setdefault(p["osm"], p)
        print(f"  part {n}/{len(todo)}: {len(data['elements'])} towns", flush=True)
    rows = sorted([round(p["lat"], 5), round(p["lon"], 5), p["place_type"], p["name"] if p["named"] else "",
                   p["name_local"], p["osm"]] for p in by_osm.values())
    s, w, n, e = FIRE_BOX
    tiles = [[i, j] for i in range(int(s / TILE_DEG), int(n / TILE_DEG)) for j in range(int(w / TILE_DEG), int(e / TILE_DEG))]
    doc = {"format": FORMAT, "created": datetime.now(IST).isoformat(timespec="seconds"),
           "osm_base": min(stamps) if stamps else None, "tile_deg": TILE_DEG, "tiles": tiles,
           "attribution": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
           "fields": ["lat", "lon", "type", "name", "name_local", "osm"], "places": rows}
    with open(OUT, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode())
    print(f"Wrote {OUT}: {len(rows):,} towns and cities, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
