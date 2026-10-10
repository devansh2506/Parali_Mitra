"""Is a point inside India?

The outline is saved by scripts/build_region.py (data/region.json.gz). The fire watch
uses this to leave out fires across the border (Pakistan, Nepal, Bangladesh ...). If the file is
missing, every point counts as inside (the fire box still limits the area).
"""

import gzip
import json
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

REGION_PATH = Path(__file__).with_name("data") / "region.json.gz"
STATES_PATH = Path(__file__).with_name("data") / "states.json.gz"  # one outline per state (scripts/build_states.py)
AREAS = ("India",)


def _inside_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class Region:
    def __init__(self, polygons):
        # [(bbox, outer ring, holes)]
        self.polygons = []
        for poly in polygons:
            xs = [p[0] for p in poly[0]]
            ys = [p[1] for p in poly[0]]
            self.polygons.append(((min(ys), min(xs), max(ys), max(xs)), poly[0], poly[1:]))

    def contains(self, lat, lon):
        for (s, w, n, e), outer, holes in self.polygons:
            if s <= lat <= n and w <= lon <= e and _inside_ring(lat, lon, outer):
                if not any(_inside_ring(lat, lon, h) for h in holes):
                    return True
        return False


@lru_cache(maxsize=1)
def get():
    """The saved outline, or None when the file is missing."""
    try:
        with gzip.open(REGION_PATH, "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
        return Region([poly for polys in doc["states"].values() for poly in polys])
    except (OSError, ValueError, KeyError) as err:
        log.warning("region outline not available: %s", err)
        return None


def contains(lat, lon, region=None):
    region = get() if region is None else region
    return True if region is None else region.contains(lat, lon)


@lru_cache(maxsize=1)
def _states():
    try:
        with gzip.open(STATES_PATH, "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
        return {name: Region(polys) for name, polys in doc["states"].items()}
    except (OSError, ValueError, KeyError) as err:
        log.warning("state outlines not available: %s", err)
        return None


def state_of(lat, lon):
    """The state or union territory a point is in ('' when unknown). The outlines are simplified, so a point
    a few km off the coast or border falls back to the state with the nearest outline point."""
    states = _states()
    if not states:
        return ""
    for name, r in states.items():
        if r.contains(lat, lon):
            return name
    best, best_d = "", 0.5  # degrees (~55 km): further than that it is not near any state
    for name, r in states.items():
        for _, outer, _ in r.polygons:
            for x, y in outer[::3]:
                d = abs(x - lon) + abs(y - lat)
                if d < best_d:
                    best, best_d = name, d
    return best
