"""Download factories, brick kilns, power plants, industrial areas and landfills around
Punjab and Haryana from OpenStreetMap once, so a fire on one is labelled industrial.

    python3.12 scripts/build_industry.py

Asks Overpass for the fire box in 4 parts (waiting for a free slot and retrying when
the server is busy), keeps each finished part in .build_cache/industry/, and writes
src/smoke_path/data/industry.json.gz. Areas are stored as a centre and a radius
(the average of half their width and half their height).

Data © OpenStreetMap contributors, ODbL 1.0.
"""

import gzip
import json
import math
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_places_snapshot import WAITS_S, wait_for_slot  # noqa: E402

from smoke_path.firewatch import FIRE_BOX  # noqa: E402
from smoke_path.landuse import INDUSTRY_PATH  # noqa: E402
from smoke_path.net import ApiError, parse_json, request  # noqa: E402
from smoke_path.places import _cut_short, overpass_url  # noqa: E402
from smoke_path.trajectory import KM_PER_DEG  # noqa: E402

CACHE = ROOT / ".build_cache" / "industry"
SERVER_TIMEOUT_S = 120
PARTS = 2  # the box is split PARTS x PARTS
NOT_BURNING = {"solar", "wind", "hydro", "photovoltaic"}  # power plants that cannot be a fire


def query(s, w, n, e):
    return (
        f"[out:json][timeout:{SERVER_TIMEOUT_S}][maxsize:134217728][bbox:{s:.3f},{w:.3f},{n:.3f},{e:.3f}];\n"
        "(\n"
        '  nwr["landuse"~"^(industrial|landfill)$"];\n'
        '  nwr["man_made"~"^(works|kiln)$"];\n'
        '  nwr["industrial"];\n'
        '  nwr["power"="plant"];\n'
        ");\n"
        "out tags center bb;"
    )


def parts():
    s, w, n, e = FIRE_BOX
    dl, dw = (n - s) / PARTS, (e - w) / PARTS
    return [(round(s + a * dl, 3), round(w + b * dw, 3), round(s + (a + 1) * dl, 3), round(w + (b + 1) * dw, 3))
            for a in range(PARTS) for b in range(PARTS)]


def fetch(box):
    body = urllib.parse.urlencode({"data": query(*box)}).encode()
    raw = request(overpass_url(), SERVER_TIMEOUT_S + 30, data=body,
                  headers={"Content-Type": "application/x-www-form-urlencoded"}, name="OpenStreetMap (Overpass)")
    data = parse_json(raw, "OpenStreetMap (Overpass)")
    if _cut_short(data) or not isinstance(data.get("elements"), list):
        raise ApiError(f"cut short: {data.get('remark', 'no elements list')}")
    return raw


def kind_of(tags):
    """Our kind for an OSM element, or None when it cannot be a fire source we care about."""
    if tags.get("landuse") == "landfill":
        return "landfill"
    if tags.get("man_made") == "kiln" or tags.get("industrial") in ("brickyard", "brickworks", "brick"):
        return "kiln"
    if tags.get("power") == "plant":
        source = (tags.get("plant:source") or tags.get("generator:source") or "").lower()
        method = (tags.get("plant:method") or "").lower()
        if source in NOT_BURNING or method in NOT_BURNING or not source:
            return None  # solar/wind/hydro, or unknown (most untagged plants here are solar farms)
        return "power"
    if tags.get("man_made") == "works" or tags.get("industrial"):
        return "works"
    if tags.get("landuse") == "industrial":
        return "industrial"
    return None


def feature(el):
    tags = el.get("tags") or {}
    kind = kind_of(tags)
    if not kind:
        return None
    if el.get("type") == "node":
        lat, lon, r_km = el.get("lat"), el.get("lon"), 0.0
    else:
        b = el.get("bounds") or {}
        if not b:
            return None
        c = el.get("center") or {"lat": (b["minlat"] + b["maxlat"]) / 2, "lon": (b["minlon"] + b["maxlon"]) / 2}
        lat, lon = c["lat"], c["lon"]
        half_h = (b["maxlat"] - b["minlat"]) / 2 * KM_PER_DEG
        half_w = (b["maxlon"] - b["minlon"]) / 2 * KM_PER_DEG * math.cos(math.radians(lat))
        r_km = (half_h + half_w) / 2
    if lat is None:
        return None
    return {"kind": kind, "name": tags.get("name:en") or tags.get("name") or "", "lat": round(lat, 5),
            "lon": round(lon, 5), "r_km": round(r_km, 3), "osm": f"{el['type'][0]}{el['id']}"}


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    elements = {}
    for n, box in enumerate(parts(), 1):
        path = CACHE / ("part_" + "_".join(f"{x:.3f}" for x in box) + ".json")
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
                path.with_suffix(".part").write_bytes(raw)
                path.with_suffix(".part").replace(path)
                break
            else:
                raise SystemExit(f"part {n} kept failing; run again later to continue")
        data = json.loads(path.read_bytes())
        for el in data["elements"]:
            elements[(el["type"], el["id"])] = el
        print(f"  part {n}/{len(parts())}: {len(data['elements'])} elements", flush=True)
    features = sorted((f for f in map(feature, elements.values()) if f), key=lambda f: (f["lat"], f["lon"]))
    doc = {"format": 1, "box": list(FIRE_BOX),
           "attribution": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
           "features": features}
    with open(INDUSTRY_PATH, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode())
    counts = {}
    for f in features:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    print(f"Wrote {INDUSTRY_PATH}: {len(features)} features {counts}")


if __name__ == "__main__":
    main()
