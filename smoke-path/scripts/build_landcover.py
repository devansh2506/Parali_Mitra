"""Save what covers the ground around Punjab and Haryana (farm, town, trees ...) as a
small grid, so each satellite fire can be labelled by what was burning.

    .venv-build/bin/python scripts/build_landcover.py

Source: ESA WorldCover 2021 v200, 10 m land cover from Sentinel-1/2, free and public
on AWS (s3://esa-worldcover). © ESA WorldCover project 2021 / Contains modified
Copernicus Sentinel data (2021) processed by ESA WorldCover consortium. CC BY 4.0.

This script needs rasterio and numpy, so it runs from a local build venv:

    python3.12 -m venv .venv-build
    .venv-build/bin/pip install rasterio numpy

The app itself stays standard-library only: it just reads the file written here,
src/smoke_path/data/landcover.bin.gz. Format: one JSON header line, then one byte
per 0.001 degree (~100 m) cell, rows from north to south, columns west to east.
Each byte is the most common WorldCover class in that cell divided by 10
(1 tree, 2 shrub, 3 grass, 4 cropland, 5 built-up, 6 bare, 7 snow, 8 water,
9 wetland, 10 mangrove, 11 moss), 0 where there is no data.
"""

import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smoke_path.firewatch import FIRE_BOX  # noqa: E402
from smoke_path.landuse import LANDCOVER_PATH, LANDCOVER_STEP  # noqa: E402

URL = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
       "ESA_WorldCover_10m_2021_v200_{name}_Map.tif")
PAD_DEG = 0.01  # so a 400 m look-around at the edge of the fire box still has data
OVERVIEW = 0  # first overview: 2x coarser (~18 m), 36 samples per 100 m cell
STRIP_ROWS = 100  # output rows handled at a time (keeps memory small)
CLASSES = 11


def box():
    s, w, n, e = FIRE_BOX
    return (round(s - PAD_DEG, 3), round(w - PAD_DEG, 3), round(n + PAD_DEG, 3), round(e + PAD_DEG, 3))


def tile_names(s, w, n, e):
    """WorldCover tiles are 3x3 degrees named by their south-west corner, e.g. N30E075."""
    names = []
    for lat in range(math.floor(s / 3) * 3, math.ceil(n / 3) * 3, 3):
        for lon in range(math.floor(w / 3) * 3, math.ceil(e / 3) * 3, 3):
            names.append(f"N{lat:02d}E{lon:03d}")
    return names


def majority(block_codes, factor):
    """Most common class in each factor x factor block (ties: lowest class code)."""
    h, w = block_codes.shape
    blocks = block_codes.reshape(h // factor, factor, w // factor, factor)
    counts = np.stack([(blocks == c).sum(axis=(1, 3)) for c in range(1, CLASSES + 1)])
    best = counts.argmax(axis=0).astype(np.uint8) + 1
    best[counts.max(axis=0) == 0] = 0
    return best


def main():
    s, w, n, e = box()
    step = LANDCOVER_STEP
    rows, cols = round((n - s) / step), round((e - w) / step)
    grid = np.zeros((rows, cols), dtype=np.uint8)
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3")
    with env:
        for name in tile_names(s, w, n, e):
            tlat, tlon = int(name[1:3]), int(name[4:7])
            ts, tw, tn, te = max(s, tlat), max(w, tlon), min(n, tlat + 3), min(e, tlon + 3)
            if ts >= tn or tw >= te:
                continue
            print(f"{name}: lat {ts}-{tn}, lon {tw}-{te}", flush=True)
            with rasterio.open(URL.format(name=name), overview_level=OVERVIEW) as src:
                px = src.res[0]
                factor = round(step / px)
                if abs(factor * px - step) > 1e-9:
                    raise SystemExit(f"{name}: pixel {px} does not divide {step}")
                r0 = round((n - tn) / step)
                c0 = round((tw - w) / step)
                out_cols = round((te - tw) / step)
                out_rows = round((tn - ts) / step)
                for r in range(0, out_rows, STRIP_ROWS):
                    nr = min(STRIP_ROWS, out_rows - r)
                    top = tn - r * step
                    win = from_bounds(tw, top - nr * step, te, top, transform=src.transform)
                    win = win.round_offsets().round_lengths()
                    data = src.read(1, window=win, boundless=True, fill_value=0)
                    data = data[: nr * factor, : out_cols * factor]
                    codes = (data // 10).astype(np.uint8)  # 10..100 -> 1..10, 95 (mangrove) -> 9 fixed below
                    codes[data == 95] = 10
                    codes[data == 100] = 11
                    grid[r0 + r: r0 + r + nr, c0: c0 + out_cols] = majority(codes, factor)
                    print(f"  {r + nr}/{out_rows} rows", end="\r", flush=True)
                print()
    header = {"format": 1, "source": "ESA WorldCover 2021 v200", "south": s, "west": w, "north": n,
              "east": e, "step": step, "rows": rows, "cols": cols}
    LANDCOVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    part = LANDCOVER_PATH.with_suffix(".part")
    with open(part, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write((json.dumps(header) + "\n").encode())
            gz.write(grid.tobytes())
    part.replace(LANDCOVER_PATH)
    shares = {c: round(float((grid == c).mean()) * 100, 1) for c in range(CLASSES + 1) if (grid == c).any()}
    print(f"Wrote {LANDCOVER_PATH} ({LANDCOVER_PATH.stat().st_size / 1e6:.1f} MB), {rows}x{cols}; % by class {shares}")


if __name__ == "__main__":
    main()
