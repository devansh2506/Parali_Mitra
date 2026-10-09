"""Find spots that burn all year (brick kilns, factories, flares) from one year of NASA
VIIRS archive data, so a fire there is labelled industrial rather than a farm fire.

    python3.12 scripts/build_static_sources.py                  # last 12 archived months
    python3.12 scripts/build_static_sources.py --start 2025-07-01 --end 2026-06-30

Uses FIRMS_MAP_KEY from smoke-path/.env. Asks NASA FIRMS for the standard-processing
(archive) VIIRS data of Suomi NPP and NOAA-20 over the fire box, 5 days per request
(~150 requests, far below the 5000 per 10 minutes limit), caching each answer in
.build_cache/firms_sp/ so a stopped run continues where it left off.

A ~400 m cell is kept when either
  - NASA classified a detection there as type 2, "other static land source"
    (industrial heat: kilns, plants, flares), or
  - fire was seen there on at least MIN_OFF_SEASON_DAYS different days outside the
    crop-burning seasons (wheat: Apr 1 - Jun 15, paddy: Sep 15 - Dec 15). Fields burn
    once or twice a year in season; kilns and factories burn month after month.

Writes src/smoke_path/data/static_sources.json.gz.
"""

import argparse
import csv
import gzip
import io
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _env import load_env  # noqa: E402

from smoke_path.fires import box_area, looks_like_firms_csv, map_key  # noqa: E402
from smoke_path.firewatch import FIRE_BOX  # noqa: E402
from smoke_path.landuse import STATIC_CELL_DEG, STATIC_PATH  # noqa: E402
from smoke_path.net import ApiError, request  # noqa: E402

SOURCES = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP")
URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/{days}/{day}"
AVAILABILITY_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{key}/ALL"
CHUNK_DAYS = 5  # the most FIRMS gives per request
CACHE = ROOT / ".build_cache" / "firms_sp"
MIN_OFF_SEASON_DAYS = 3
PAUSE_S = 1


def in_crop_season(d):
    md = (d.month, d.day)
    return (4, 1) <= md <= (6, 15) or (9, 15) <= md <= (12, 15)


def fetch(url, key, name, fire_csv=True):
    try:
        text = request(url, 60, name=name).decode("utf-8", errors="replace")
    except ApiError as err:
        raise ApiError(str(err).replace(key, "***")) from None
    if fire_csv and not looks_like_firms_csv(text):
        raise ApiError(f"{name}: not fire data ({' '.join(text.split())[:80].replace(key, '***')})")
    return text


def last_archive_day(key):
    text = fetch(AVAILABILITY_URL.format(key=key), key, "FIRMS availability", fire_csv=False)
    ends = [date.fromisoformat(r["max_date"]) for r in csv.DictReader(io.StringIO(text)) if r["data_id"] in SOURCES]
    return min(ends)


def chunk_text(source, day, key):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{source}_{day.isoformat()}.csv"
    if path.exists():
        return path.read_text()
    url = URL.format(key=key, source=source, area=box_area(FIRE_BOX), days=CHUNK_DAYS, day=day.isoformat())
    for wait in (0, 10, 30, 60):
        time.sleep(wait)
        try:
            text = fetch(url, key, f"FIRMS {source} {day}")
            break
        except ApiError as err:
            print(f"  {err}; retrying", flush=True)
    else:
        raise SystemExit(f"FIRMS kept failing for {source} {day}; run again later to continue")
    path.write_text(text)
    time.sleep(PAUSE_S)
    return text


def cells_from(rows):
    cells = {}
    for r in rows:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
            day = date.fromisoformat(r["acq_date"])
        except (KeyError, ValueError):
            continue
        k = (round(lat / STATIC_CELL_DEG), round(lon / STATIC_CELL_DEG))
        c = cells.setdefault(k, {"lat": 0.0, "lon": 0.0, "n": 0, "off_days": set(), "type2": False})
        c["lat"] += lat
        c["lon"] += lon
        c["n"] += 1
        if not in_crop_season(day):
            c["off_days"].add(day)
        if (r.get("type") or "").strip() == "2":
            c["type2"] = True
    return cells


def keep(cells, period):
    out = []
    for c in cells.values():
        if c["type2"] or len(c["off_days"]) >= MIN_OFF_SEASON_DAYS:
            out.append({"lat": round(c["lat"] / c["n"], 5), "lon": round(c["lon"] / c["n"], 5),
                        "days": len(c["off_days"]), "detections": c["n"], "type2": c["type2"], "period": period})
    out.sort(key=lambda r: (r["lat"], r["lon"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--start", type=date.fromisoformat)
    ap.add_argument("--end", type=date.fromisoformat)
    args = ap.parse_args(argv)
    load_env()
    key = map_key()
    if not key:
        raise SystemExit("FIRMS_MAP_KEY is not set (smoke-path/.env)")
    end = args.end or last_archive_day(key)
    start = args.start or (end - timedelta(days=364))
    print(f"VIIRS archive {start} to {end} over {FIRE_BOX}")
    rows = []
    for source in SOURCES:
        day = start
        while day <= end:
            text = chunk_text(source, day, key)
            rows.extend(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
            print(f"  {source} {day}: {len(rows)} detections so far", end="\r", flush=True)
            day += timedelta(days=CHUNK_DAYS)
        print()
    period = f"{start:%b %Y} to {end:%b %Y}"
    cells = cells_from(rows)
    kept = keep(cells, period)
    doc = {"format": 1, "source": "NASA FIRMS VIIRS standard processing (" + ", ".join(SOURCES) + ")",
           "period": period, "box": list(FIRE_BOX), "cell_deg": STATIC_CELL_DEG,
           "min_off_season_days": MIN_OFF_SEASON_DAYS, "cells": kept}
    STATIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATIC_PATH, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(json.dumps(doc, separators=(",", ":")).encode())
    t2 = sum(1 for c in kept if c["type2"])
    print(f"{len(rows)} detections in {len(cells)} cells; kept {len(kept)} static sources ({t2} NASA type 2)")
    print(f"Wrote {STATIC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
