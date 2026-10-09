"""Saved copy of OpenStreetMap places around Punjab and Haryana (Option B).

The public Overpass server is often overloaded, and villages, schools and
hospitals do not move, so we download them once (scripts/build_places_snapshot.py)
and ship the file with the Lambda. Looking places up here takes milliseconds.

The area is stored as 0.5 degree tiles. Only tiles that downloaded completely
are listed, so a point is "covered" only when every tile within reach of it was
saved; anything else goes to live Overpass instead of being treated as empty.

Data © OpenStreetMap contributors, available under the ODbL.
"""

import gzip
import json
import logging
import math
from pathlib import Path

from .places import AMENITY_RADIUS_M, TOWN_RADIUS_M, VILLAGE_RADIUS_M
from .trajectory import KM_PER_DEG

log = logging.getLogger(__name__)

SNAPSHOT_PATH = Path(__file__).with_name("data") / "places_snapshot.json.gz"
FORMAT = 1
GRID_DEG = 0.1  # lookup grid (finer than the download tiles)

RADIUS_KM = {
    "city": TOWN_RADIUS_M / 1000,
    "town": TOWN_RADIUS_M / 1000,
    "village": VILLAGE_RADIUS_M / 1000,
    "school": AMENITY_RADIUS_M / 1000,
    "college": AMENITY_RADIUS_M / 1000,
    "hospital": AMENITY_RADIUS_M / 1000,
    "clinic": AMENITY_RADIUS_M / 1000,
}
MAX_RADIUS_KM = max(RADIUS_KM.values())


def tile_of(lat, lon, tile_deg):
    return (math.floor(lat / tile_deg), math.floor(lon / tile_deg))


def distance_to_line_km(lat, lon, line):
    """Shortest distance (km) from a point to a polyline of (lat, lon), flat projection."""
    coslat = math.cos(math.radians(lat))
    pts = [((lo - lon) * KM_PER_DEG * coslat, (la - lat) * KM_PER_DEG) for la, lo in line]
    if len(pts) == 1:
        return math.hypot(*pts[0])
    best = math.inf
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        f = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
        best = min(best, math.hypot(ax + f * dx, ay + f * dy))
    return best


def _pad_deg(lat, km):
    """(lat padding, lon padding) in degrees for `km` around latitude `lat`."""
    return km / KM_PER_DEG, km / (KM_PER_DEG * max(math.cos(math.radians(lat)), 0.01))


def _segment_distance(ax, ay, bx, by):
    """(distance, f) from the origin to segment a-b; f in [0, 1] is where the closest point is."""
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    f = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
    return math.hypot(ax + f * dx, ay + f * dy), f


class Snapshot:
    def __init__(self, doc):
        if doc.get("format") != FORMAT:
            raise ValueError(f"places snapshot format {doc.get('format')!r} is not {FORMAT}")
        self.tile_deg = float(doc["tile_deg"])
        self.tiles = {tuple(t) for t in doc["tiles"]}
        self.osm_base = doc.get("osm_base")
        self.created = doc.get("created")
        self.rows = [tuple(r) for r in doc["places"]]  # (lat, lon, type, name, name_local, osm)
        # One lookup grid per search distance, so each segment only looks as far as it must.
        self.grids = {}
        for i, row in enumerate(self.rows):
            radius = RADIUS_KM.get(row[2])
            if radius is None:
                continue
            key = (math.floor(row[0] / GRID_DEG), math.floor(row[1] / GRID_DEG))
            self.grids.setdefault(radius, {}).setdefault(key, []).append(i)

    @classmethod
    def load(cls, path=SNAPSHOT_PATH):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def covers(self, lat, lon, margin_km=MAX_RADIUS_KM):
        """True if every saved tile within `margin_km` of the point is present."""
        dlat, dlon = _pad_deg(lat, margin_km)
        lo = tile_of(lat - dlat, lon - dlon, self.tile_deg)
        hi = tile_of(lat + dlat, lon + dlon, self.tile_deg)
        return all((i, j) in self.tiles for i in range(lo[0], hi[0] + 1) for j in range(lo[1], hi[1] + 1))

    def near_segments(self, line):
        """{row index: (distance_km, segment index, f)} for saved places within their type's
        distance of the line (towns 15 km, villages 5 km, schools and hospitals 3 km).

        f is how far along that segment the closest point is, so callers can interpolate the
        time the smoke is there without measuring again.
        """
        best = {}
        segments = list(zip(line, line[1:])) or [(line[0], line[0])]
        for s_idx, ((la1, lo1), (la2, lo2)) in enumerate(segments):
            mid = (la1 + la2) / 2
            coslat = math.cos(math.radians(mid))
            for radius, grid in self.grids.items():
                dlat, dlon = _pad_deg(mid, radius)
                i0 = math.floor((min(la1, la2) - dlat) / GRID_DEG)
                i1 = math.floor((max(la1, la2) + dlat) / GRID_DEG)
                j0 = math.floor((min(lo1, lo2) - dlon) / GRID_DEG)
                j1 = math.floor((max(lo1, lo2) + dlon) / GRID_DEG)
                for i in range(i0, i1 + 1):
                    for j in range(j0, j1 + 1):
                        for idx in grid.get((i, j), ()):
                            lat, lon = self.rows[idx][0], self.rows[idx][1]
                            d, f = _segment_distance(
                                (lo1 - lon) * KM_PER_DEG * coslat,
                                (la1 - lat) * KM_PER_DEG,
                                (lo2 - lon) * KM_PER_DEG * coslat,
                                (la2 - lat) * KM_PER_DEG,
                            )
                            if d <= radius and (idx not in best or d < best[idx][0] - 1e-9):
                                best[idx] = (d, s_idx, f)
        return best

    def place(self, idx):
        lat, lon, ptype, name, local, osm = self.rows[idx]
        return {
            "name": name or f"Unnamed {ptype}",
            "name_local": local,
            "place_type": ptype,
            "named": bool(name),
            "lat": lat,
            "lon": lon,
            "osm": osm,
        }

    def near(self, line):
        """Saved places within their type's distance of the line, as place dicts."""
        return [self.place(idx) for idx in sorted(self.near_segments(line))]

    def nearest(self, lat, lon, types=("village", "town", "city"), max_km=5.0):
        """The closest named place of these types within max_km, as a place dict, or None."""
        best, best_d = None, max_km
        for radius, grid in self.grids.items():
            dlat, dlon = _pad_deg(lat, max_km)
            for i in range(math.floor((lat - dlat) / GRID_DEG), math.floor((lat + dlat) / GRID_DEG) + 1):
                for j in range(math.floor((lon - dlon) / GRID_DEG), math.floor((lon + dlon) / GRID_DEG) + 1):
                    for idx in grid.get((i, j), ()):
                        row = self.rows[idx]
                        if row[2] not in types or not row[3]:
                            continue
                        d = distance_to_line_km(lat, lon, [(row[0], row[1])])
                        if d <= best_d:
                            best, best_d = idx, d
        return None if best is None else self.place(best)


_cache = {}


def get(path=SNAPSHOT_PATH):
    """The shipped snapshot (loaded once per warm Lambda), or None if there is none."""
    key = str(path)
    if key not in _cache:
        try:
            _cache[key] = Snapshot.load(path)
        except FileNotFoundError:
            _cache[key] = None
        except (OSError, ValueError, KeyError, TypeError) as err:
            log.warning("places snapshot unusable, using live Overpass only: %r", err)
            _cache[key] = None
    return _cache[key]
