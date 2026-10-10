"""Save the outline of every Indian state and union territory, so each fire can be given its state
(the authority screens filter by it).

    python3.12 scripts/build_states.py

One request per state to OpenStreetMap's Nominatim (simplified outlines, about 2 km accuracy), waiting 2 s
between requests as Nominatim asks. Written to src/smoke_path/data/states.json.gz.

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
from smoke_path.region import STATES_PATH  # noqa: E402

# (name we show, search text)
STATES = [
    ("Andaman and Nicobar Islands", "Andaman and Nicobar Islands"), ("Andhra Pradesh", "Andhra Pradesh"),
    ("Arunachal Pradesh", "Arunachal Pradesh"), ("Assam", "Assam"), ("Bihar", "Bihar"), ("Chandigarh", "Chandigarh"),
    ("Chhattisgarh", "Chhattisgarh"), ("Dadra and Nagar Haveli and Daman and Diu", "Dadra and Nagar Haveli and Daman and Diu"),
    ("Delhi", "Delhi"), ("Goa", "Goa"), ("Gujarat", "Gujarat"), ("Haryana", "Haryana"), ("Himachal Pradesh", "Himachal Pradesh"),
    ("Jammu and Kashmir", "Jammu and Kashmir"), ("Jharkhand", "Jharkhand"), ("Karnataka", "Karnataka"), ("Kerala", "Kerala"),
    ("Ladakh", "Ladakh"), ("Lakshadweep", "Lakshadweep"), ("Madhya Pradesh", "Madhya Pradesh"), ("Maharashtra", "Maharashtra"),
    ("Manipur", "Manipur"), ("Meghalaya", "Meghalaya"), ("Mizoram", "Mizoram"), ("Nagaland", "Nagaland"), ("Odisha", "Odisha"),
    ("Puducherry", "Puducherry"), ("Punjab", "Punjab"), ("Rajasthan", "Rajasthan"), ("Sikkim", "Sikkim"),
    ("Tamil Nadu", "Tamil Nadu"), ("Telangana", "Telangana"), ("Tripura", "Tripura"), ("Uttar Pradesh", "Uttar Pradesh"),
    ("Uttarakhand", "Uttarakhand"), ("West Bengal", "West Bengal"),
]


def search(text, **extra):
    params = {"q": f"{text}, India", "format": "geojson", "polygon_geojson": 1, "polygon_threshold": 0.02,
              "limit": 5, "countrycodes": "in", **extra}
    raw = request("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params), 90,
                  headers={"User-Agent": "ParaliMitra-hackathon/1.0"}, name="OpenStreetMap (Nominatim)")
    return [f for f in json.loads(raw)["features"] if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]


def outline(name, text):
    feats = search(text, featuretype="state")
    time.sleep(2)
    if not feats:
        feats = search(text)
        time.sleep(2)
    feats = [f for f in feats if f["properties"].get("display_name", "").startswith(text)]
    if not feats:
        raise SystemExit(f"no outline found for {name}")
    g = max(feats, key=lambda f: len(json.dumps(f["geometry"])))["geometry"]  # the state, not a district of the same name
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [[[[round(x, 3), round(y, 3)] for x, y in ring] for ring in poly] for poly in polys]


def main():
    states = {}
    for name, text in STATES:
        states[name] = outline(name, text)
        print(f"  {name}: {len(states[name])} polygons, {sum(len(r) for p in states[name] for r in p)} points", flush=True)
    doc = {"format": 1, "attribution": "© OpenStreetMap contributors, ODbL 1.0", "states": states}
    with open(STATES_PATH, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(json.dumps(doc, separators=(",", ":")).encode())
    print(f"Wrote {STATES_PATH} ({STATES_PATH.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
