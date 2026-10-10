"""Save the outline of India (OpenStreetMap's, which includes Jammu and Kashmir and the islands), so the
fire watch can leave out fires across the border (Pakistan, Nepal, Bangladesh, Myanmar ...).

    python3.12 scripts/build_region.py

One request to OpenStreetMap's Nominatim (simplified outline, about 2 km accuracy), written to
src/smoke_path/data/region.json.gz.

Data © OpenStreetMap contributors, ODbL 1.0.
"""

import gzip
import json
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smoke_path.net import request  # noqa: E402
from smoke_path.region import AREAS, REGION_PATH  # noqa: E402


def outline(name):
    params = {"country": name, "format": "geojson", "polygon_geojson": 1, "polygon_threshold": 0.02, "limit": 1}
    raw = request("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params), 90,
                  headers={"User-Agent": "ParaliMitra-hackathon/1.0"}, name="OpenStreetMap (Nominatim)")
    feats = [f for f in json.loads(raw)["features"] if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
    if not feats:
        raise SystemExit(f"no outline found for {name}")
    g = feats[0]["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [[[[round(x, 3), round(y, 3)] for x, y in ring] for ring in poly] for poly in polys]


def main():
    states = {}
    for name in AREAS:
        states[name] = outline(name)
        n = sum(len(r) for p in states[name] for r in p)
        print(f"  {name}: {len(states[name])} polygons, {n} points", flush=True)
        time.sleep(2)  # Nominatim allows one request per second
    doc = {"format": 1, "attribution": "© OpenStreetMap contributors, ODbL 1.0", "states": states}
    with open(REGION_PATH, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(json.dumps(doc, separators=(",", ":")).encode())
    print(f"Wrote {REGION_PATH} ({REGION_PATH.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
