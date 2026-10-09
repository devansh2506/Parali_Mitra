"""Download villages, towns, schools and hospitals around Punjab and Haryana once,
and save them as src/smoke_path/data/places_snapshot.json.gz (Option B).

    python3.12 scripts/build_places_snapshot.py
    python3.12 scripts/build_places_snapshot.py --box 27.5,72.5,33.0,78.5

The default box (lat 27.5-33.0, lon 72.5-78.5) covers Punjab, Haryana, Chandigarh,
Delhi, north Rajasthan, south Himachal, Jammu and east Pakistan Punjab, where smoke
from a Punjab field usually travels in 24-48 hours.

It asks Overpass for one 0.5 degree tile at a time, waits and retries when the
server is busy, and keeps every finished tile in .snapshot_cache/, so you can stop
it (Ctrl+C) and run it again later to continue. Tiles that never finish are left
out of the snapshot; the app then uses live Overpass for paths that reach them.

Data © OpenStreetMap contributors, ODbL 1.0.
"""

import argparse
import gzip
import json
import math
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smoke_path import IST  # noqa: E402
from smoke_path.net import ApiError, parse_json, request  # noqa: E402
from smoke_path.places import _cut_short, overpass_url, parse_overpass  # noqa: E402
from smoke_path.snapshot import FORMAT, SNAPSHOT_PATH  # noqa: E402

TILE_DEG = 0.5
DEFAULT_BOX = (27.5, 72.5, 33.0, 78.5)  # south, west, north, east
CACHE = ROOT / ".snapshot_cache"
SERVER_TIMEOUT_S = 45
# A small declared budget gets a query admitted sooner on a busy server; a dense tile needs ~0.5 MB.
SERVER_MAXSIZE = 64 * 1024 * 1024
WAITS_S = (15, 30, 60, 120, 180, 300)  # pauses between retries of one tile (429 / refused need minutes)
CORE = (30.6, 75.8)  # between Punjab and Haryana: tiles nearest this are fetched first
PAUSE_S = 3  # be polite between tiles
MAX_SLOT_WAIT_S = 300


def tiles_in(box):
    s, w, n, e = box
    i0, i1 = round(s / TILE_DEG), round(n / TILE_DEG)
    j0, j1 = round(w / TILE_DEG), round(e / TILE_DEG)
    return [(i, j) for i in range(i0, i1) for j in range(j0, j1)]


SPLIT_AFTER = 2  # after this many failed tries, fetch the tile as 4 quarter tiles


def tile_query(i, j):
    s, w = i * TILE_DEG, j * TILE_DEG
    return box_query(s, w, s + TILE_DEG, w + TILE_DEG)


def box_query(s, w, n, e):
    bbox = f"{s:.3f},{w:.3f},{n:.3f},{e:.3f}"
    return (
        f"[out:json][timeout:{SERVER_TIMEOUT_S}][maxsize:{SERVER_MAXSIZE}][bbox:{bbox}];\n"
        "(\n"
        '  node["place"~"^(city|town|village)$"];\n'
        '  nwr["amenity"~"^(school|college|hospital|clinic)$"];\n'
        ");\n"
        "out center tags;"
    )


def cache_file(i, j):
    return CACHE / f"tile_{i}_{j}.json"


def slot_wait_s(status_text):
    """Seconds until Overpass gives us a query slot: 0 if free now, None if the page is unclear."""
    if re.search(r"\b\d+ slots? available now", status_text):
        return 0
    waits = [int(x) for x in re.findall(r"in (-?\d+) seconds", status_text)]
    return max(0, min(waits)) if waits else None


def fetch_status():
    """Overpass's own status page for our address (rate limit and free slots)."""
    url = overpass_url().rsplit("/", 1)[0] + "/status"
    return request(url, 15, name="Overpass status").decode("utf-8", errors="replace")


def wait_for_slot(status=fetch_status, sleep=time.sleep):
    """Wait until Overpass says a query slot is free (at most MAX_SLOT_WAIT_S)."""
    try:
        wait = slot_wait_s(status())
    except ApiError:
        return  # status page down too; the retry pauses handle it
    if wait:
        print(f"    Overpass says our next slot is free in {wait} s; waiting ...")
        sleep(min(wait + 1, MAX_SLOT_WAIT_S))


def fetch_tile(i, j):
    """Raw JSON bytes for one complete tile. Raises ApiError when the server cuts it short."""
    return fetch_query(tile_query(i, j))


def fetch_tile_split(i, j, fetch=None):
    """The same tile as 4 lighter quarter-tile queries, merged into one reply (raw JSON bytes)."""
    fetch = fetch or (lambda q: fetch_query(q))
    s, w, half = i * TILE_DEG, j * TILE_DEG, TILE_DEG / 2
    merged, seen, stamps = [], set(), []
    for qs, qw in ((s, w), (s, w + half), (s + half, w), (s + half, w + half)):
        data = json.loads(fetch(box_query(qs, qw, qs + half, qw + half)))
        stamp = (data.get("osm3s") or {}).get("timestamp_osm_base")
        if stamp:
            stamps.append(stamp)
        for el in data["elements"]:
            key = (el.get("type"), el.get("id"))
            if key not in seen:  # a way crossing quarters comes back twice
                seen.add(key)
                merged.append(el)
    osm3s = {"timestamp_osm_base": min(stamps)} if stamps else {}
    return json.dumps({"version": 0.6, "osm3s": osm3s, "elements": merged, "split": 4}).encode("utf-8")


def fetch_query(query):
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    raw = request(
        overpass_url(),
        SERVER_TIMEOUT_S + 30,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        name="OpenStreetMap (Overpass)",
    )
    data = parse_json(raw, "OpenStreetMap (Overpass)")
    if _cut_short(data) or not isinstance(data.get("elements"), list):
        raise ApiError(f"tile cut short: {data.get('remark', 'no elements list')}")
    return raw


def priority(tile):
    """Distance (in degrees) of a tile's centre from CORE: Punjab and Haryana come first."""
    i, j = tile
    return math.hypot((i + 0.5) * TILE_DEG - CORE[0], (j + 0.5) * TILE_DEG - CORE[1])


def download(tiles, fetch=fetch_tile, sleep=time.sleep, status=fetch_status, fetch_split=fetch_tile_split):
    """Fetch missing tiles into the cache, most useful first. Returns the tiles that failed.

    A tile that fails SPLIT_AFTER times is fetched as 4 quarter tiles instead (lighter queries).
    """
    CACHE.mkdir(exist_ok=True)
    failed = []
    todo = sorted((t for t in tiles if not cache_file(*t).exists()), key=priority)
    print(f"{len(tiles)} tiles, {len(tiles) - len(todo)} already saved, {len(todo)} to download")
    for n, (i, j) in enumerate(todo, 1):
        label = f"[{n}/{len(todo)}] tile {i * TILE_DEG:.1f},{j * TILE_DEG:.1f}"
        for attempt, wait in enumerate((0,) + WAITS_S):
            if wait:
                print(f"    busy, waiting {wait} s ...")
                sleep(wait)
            wait_for_slot(status, sleep)
            t0 = time.monotonic()
            split = attempt >= SPLIT_AFTER
            try:
                raw = fetch_split(i, j) if split else fetch(i, j)
            except (ApiError, ValueError, KeyError) as err:
                print(f"  {label}{' (as 4 quarters)' if split else ''}: {err}")
                continue
            cache_file(i, j).write_bytes(raw)
            print(f"  {label}: ok{' (as 4 quarters)' if split else ''}, {len(raw) // 1024} KB in {time.monotonic() - t0:.1f} s")
            break
        else:
            failed.append((i, j))
            print(f"  {label}: GAVE UP (run the script again later to retry)")
        sleep(PAUSE_S)
    return failed


def build(tiles, out=SNAPSHOT_PATH):
    """Merge cached tiles into the snapshot file. Returns (places, tiles used)."""
    by_osm = {}
    used = []
    osm_base = None
    for i, j in tiles:
        path = cache_file(i, j)
        if not path.exists():
            continue
        data = json.loads(path.read_bytes())
        used.append([i, j])
        stamp = (data.get("osm3s") or {}).get("timestamp_osm_base")
        if stamp and (osm_base is None or stamp < osm_base):
            osm_base = stamp  # the oldest tile decides how fresh the snapshot is
        for p in parse_overpass(data):
            by_osm.setdefault(p["osm"], p)  # a way crossing tiles appears twice
    rows = sorted(
        [round(p["lat"], 5), round(p["lon"], 5), p["place_type"], p["name"] if p["named"] else "", p["name_local"], p["osm"]]
        for p in by_osm.values()
    )
    doc = {
        "format": FORMAT,
        "created": datetime.now(IST).isoformat(timespec="seconds"),
        "osm_base": osm_base,
        "tile_deg": TILE_DEG,
        "tiles": sorted(used),
        "attribution": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
        "fields": ["lat", "lon", "type", "name", "name_local", "osm"],
        "places": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(out, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(payload)
    return rows, used


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--box", default=",".join(str(x) for x in DEFAULT_BOX), help="south,west,north,east")
    parser.add_argument("--build-only", action="store_true", help="no network: rebuild the file from .snapshot_cache/")
    args = parser.parse_args()
    box = tuple(float(x) for x in args.box.split(","))
    tiles = tiles_in(box)
    failed = [] if args.build_only else download(tiles)
    rows, used = build(tiles)
    counts = {}
    for r in rows:
        counts[r[2]] = counts.get(r[2], 0) + 1
    size = SNAPSHOT_PATH.stat().st_size
    print(f"\nWrote {SNAPSHOT_PATH.relative_to(ROOT)}: {len(rows):,} places, {size / 1e6:.1f} MB, {len(used)}/{len(tiles)} tiles")
    print("  " + ", ".join(f"{k} {v:,}" for k, v in sorted(counts.items())))
    missing = len(tiles) - len(used)
    if missing:
        print(f"  {missing} tiles missing{' (' + str(len(failed)) + ' failed this run)' if failed else ''}: "
              "run the script again later to fill them in.")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
