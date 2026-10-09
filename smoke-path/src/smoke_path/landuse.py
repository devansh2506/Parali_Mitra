"""What was burning: label a satellite fire as a farm, factory, town, forest ... fire.

Three saved files (built once by the scripts in scripts/, shipped with the Lambda):

  data/landcover.bin.gz        ESA WorldCover 2021 (10 m satellite land cover), as the most
                               common class in each ~100 m cell (scripts/build_landcover.py)
  data/industry.json.gz        factories, brick kilns, power plants, industrial areas and
                               landfills from OpenStreetMap (scripts/build_industry.py)
  data/static_sources.json.gz  spots NASA saw burning outside the crop-burning seasons, or
                               flagged as a static industrial heat source, over one year
                               of VIIRS archive data (scripts/build_static_sources.py)

A VIIRS fire pixel is ~375 m wide, so we look at what covers the ground within 400 m
of the detection rather than at one point. Any file can be missing: the label then
uses what is there and says less.
"""

import gzip
import json
import logging
import math
from functools import lru_cache
from pathlib import Path

from .trajectory import KM_PER_DEG

log = logging.getLogger(__name__)

DATA = Path(__file__).with_name("data")
LANDCOVER_PATH = DATA / "landcover.bin.gz"
INDUSTRY_PATH = DATA / "industry.json.gz"
STATIC_PATH = DATA / "static_sources.json.gz"

LANDCOVER_STEP = 0.001  # degrees (~100 m)
LOOK_KM = 0.4  # what is on the ground within this distance of the fire
POINT_REACH_KM = 0.4  # a mapped kiln/factory point this close counts
AREA_MARGIN_KM = 0.2  # ... and an industrial area's outline (approximated by a circle) plus this
STATIC_CELL_DEG = 0.004  # cells of the static-source list (~400 m)
INDEX_DEG = 0.05

COVER = {1: "trees", 2: "shrubs", 3: "grass", 4: "cropland", 5: "built-up", 6: "bare ground",
         7: "snow", 8: "water", 9: "wetland", 10: "mangroves", 11: "moss"}

CATEGORIES = ("farm", "industrial", "waste", "settlement", "forest", "grassland", "unknown")
LABELS = {
    "farm": "Farm fire",
    "industrial": "Industrial fire",
    "waste": "Landfill / waste fire",
    "settlement": "Fire in a built-up area",
    "forest": "Forest / tree fire",
    "grassland": "Grassland fire",
    "unknown": "Unknown",
}
INDUSTRY_KINDS = {
    "kiln": "brick kiln",
    "power": "power plant",
    "works": "factory",
    "industrial": "industrial area",
    "landfill": "landfill",
}


def _cos(lat):
    return math.cos(math.radians(lat))


class Landcover:
    def __init__(self, header, cells):
        self.south, self.west = header["south"], header["west"]
        self.north, self.east = header["north"], header["east"]
        self.step = header["step"]
        self.rows, self.cols = header["rows"], header["cols"]
        if len(cells) != self.rows * self.cols:
            raise ValueError("landcover size does not match its header")
        self.cells = cells

    def covers(self, lat, lon):
        return self.south <= lat <= self.north and self.west <= lon <= self.east

    def fractions(self, lat, lon, km=LOOK_KM):
        """Share of each land cover within km of the point, or None outside the grid."""
        if not self.covers(lat, lon):
            return None
        dlat = km / KM_PER_DEG
        dlon = km / (KM_PER_DEG * _cos(lat))
        r0 = max(0, int((self.north - (lat + dlat)) / self.step))
        r1 = min(self.rows - 1, int((self.north - (lat - dlat)) / self.step))
        c0 = max(0, int((lon - dlon - self.west) / self.step))
        c1 = min(self.cols - 1, int((lon + dlon - self.west) / self.step))
        counts = {}
        total = 0
        for r in range(r0, r1 + 1):
            clat = self.north - (r + 0.5) * self.step
            row = r * self.cols
            for c in range(c0, c1 + 1):
                clon = self.west + (c + 0.5) * self.step
                if ((clat - lat) / dlat) ** 2 + ((clon - lon) / dlon) ** 2 > 1:
                    continue
                code = self.cells[row + c]
                if code == 0:
                    continue
                counts[code] = counts.get(code, 0) + 1
                total += 1
        if not total:
            return None
        return {COVER.get(code, "other"): n / total for code, n in counts.items()}


class Industry:
    """Mapped industrial features, each a point with a radius (0 for a single node)."""

    def __init__(self, rows):
        self.rows = rows
        self.index = {}
        for i, f in enumerate(rows):
            reach_deg = (f["r_km"] + POINT_REACH_KM) / KM_PER_DEG
            for a in range(math.floor((f["lat"] - reach_deg) / INDEX_DEG), math.floor((f["lat"] + reach_deg) / INDEX_DEG) + 1):
                span = reach_deg / _cos(f["lat"])
                for b in range(math.floor((f["lon"] - span) / INDEX_DEG), math.floor((f["lon"] + span) / INDEX_DEG) + 1):
                    self.index.setdefault((a, b), []).append(i)

    def near(self, lat, lon):
        """Closest feature the point is on or next to: (feature, km from its edge), or None."""
        best = None
        for i in self.index.get((math.floor(lat / INDEX_DEG), math.floor(lon / INDEX_DEG)), ()):
            f = self.rows[i]
            d = math.hypot((f["lat"] - lat) * KM_PER_DEG, (f["lon"] - lon) * KM_PER_DEG * _cos(lat))
            edge = d - f["r_km"]
            limit = POINT_REACH_KM if f["r_km"] == 0 else AREA_MARGIN_KM
            if edge <= limit and (best is None or edge < best[1]):
                best = (f, max(0.0, edge))
        return best


class StaticSources:
    def __init__(self, rows):
        self.cells = {(round(r["lat"] / STATIC_CELL_DEG), round(r["lon"] / STATIC_CELL_DEG)): r for r in rows}

    def near(self, lat, lon):
        a, b = round(lat / STATIC_CELL_DEG), round(lon / STATIC_CELL_DEG)
        best = None
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                r = self.cells.get((a + da, b + db))
                if not r:
                    continue
                d = math.hypot((r["lat"] - lat) * KM_PER_DEG, (r["lon"] - lon) * KM_PER_DEG * _cos(lat))
                if d <= LOOK_KM and (best is None or d < best[1]):
                    best = (r, d)
        return best


def _read_json_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def landcover():
    try:
        with gzip.open(LANDCOVER_PATH, "rb") as f:
            header = json.loads(f.readline())
            return Landcover(header, f.read())
    except (OSError, ValueError, KeyError) as err:
        log.warning("land cover not available: %s", err)
        return None


@lru_cache(maxsize=1)
def industry():
    try:
        return Industry(_read_json_gz(INDUSTRY_PATH)["features"])
    except (OSError, ValueError, KeyError) as err:
        log.warning("industry list not available: %s", err)
        return None


@lru_cache(maxsize=1)
def static_sources():
    try:
        return StaticSources(_read_json_gz(STATIC_PATH)["cells"])
    except (OSError, ValueError, KeyError) as err:
        log.warning("static heat sources not available: %s", err)
        return None


def _pct(x):
    return round(x * 100)


def _top(fr, k=3):
    return {name: _pct(v) for name, v in sorted(fr.items(), key=lambda kv: -kv[1])[:k] if _pct(v) > 0}


def _result(category, kind, confidence, reason, cover):
    return {"category": category, "label": LABELS[category], "kind": kind,
            "confidence": confidence, "reason": reason, "cover": cover}


def classify(lat, lon, lc=None, ind=None, sta=None):
    """Label one fire detection. Pass the data objects to override the shipped files."""
    lc = landcover() if lc is None else lc
    ind = industry() if ind is None else ind
    sta = static_sources() if sta is None else sta
    fr = lc.fractions(lat, lon) if lc else None
    cover = _top(fr) if fr else {}
    crop = fr.get("cropland", 0) if fr else 0

    hit = sta.near(lat, lon) if sta else None
    if hit:
        r, _ = hit
        why = ("NASA marks this spot as a static industrial heat source" if r.get("type2")
               else f"NASA saw fire here on {r['days']} days outside the crop-burning seasons in {r['period']}")
        return _result("industrial", "fixed heat source (kiln / factory)", "high", why, cover)

    near = ind.near(lat, lon) if ind else None
    if near:
        f, edge_km = near
        kind = INDUSTRY_KINDS.get(f["kind"], "industrial site")
        named = f" ({f['name']})" if f.get("name") else ""
        where = "inside" if edge_km == 0 and f["r_km"] > 0 else f"{round(edge_km * 1000, -1):.0f} m from"
        if f["kind"] == "landfill":
            return _result("waste", "landfill", "high" if edge_km == 0 else "medium",
                           f"{where} a mapped landfill{named} (OpenStreetMap)", cover)
        if crop >= 0.7 and not (edge_km == 0 and f["r_km"] > 0):
            return _result("farm", "crop residue", "low",
                           f"{_pct(crop)}% cropland around it, but a {kind}{named} is mapped {where.split(' from')[0]} away; "
                           "it could also be the " + kind, cover)
        return _result("industrial", kind, "medium" if edge_km else "high",
                       f"{where} a mapped {kind}{named} (OpenStreetMap)", cover)

    if not fr:
        return _result("unknown", None, "low", "outside the saved land-cover area", cover)

    trees = fr.get("trees", 0) + fr.get("shrubs", 0) + fr.get("mangroves", 0)
    built = fr.get("built-up", 0)
    grass = fr.get("grass", 0)
    src = " within 400 m (ESA WorldCover 2021 satellite land cover)"
    if crop >= 0.5:
        return _result("farm", "crop residue", "high" if crop >= 0.75 else "medium", f"{_pct(crop)}% cropland{src}", cover)
    if built >= 0.4:
        return _result("settlement", "waste or building fire", "high" if built >= 0.6 else "medium",
                       f"{_pct(built)}% built-up{src}", cover)
    if trees >= 0.5:
        return _result("forest", "trees / shrubs", "high" if trees >= 0.75 else "medium", f"{_pct(trees)}% trees and shrubs{src}", cover)
    if grass >= 0.5:
        return _result("grassland", "grass", "medium", f"{_pct(grass)}% grass{src}", cover)
    groups = {"farm": crop, "settlement": built, "forest": trees, "grassland": grass}
    category, share = max(groups.items(), key=lambda kv: kv[1])
    if share < 0.25:
        return _result("unknown", None, "low", f"mixed ground: {', '.join(f'{k} {v}%' for k, v in cover.items())}", cover)
    kind = {"farm": "crop residue", "settlement": "waste or building fire", "forest": "trees / shrubs", "grassland": "grass"}[category]
    return _result(category, kind, "low", f"mixed ground, mostly {next(iter(cover))} ({_pct(share)}%){src}", cover)


def classify_cluster(points, **data):
    """One label for a group of detections of the same fire: [(lat, lon), ...] (centre first).

    An industrial, landfill or static-source hit on any detection wins (a kiln is one spot,
    the field next to it is not). Otherwise the most common category, the centre breaking ties.
    """
    labels = [classify(lat, lon, **data) for lat, lon in points]
    strong = [x for x in labels if x["category"] in ("industrial", "waste") and x["confidence"] != "low"]
    if strong:
        return strong[0]
    votes = {}
    for x in labels:
        votes[x["category"]] = votes.get(x["category"], 0) + 1
    top = max(votes.values())
    for x in labels:  # first (the centre) among the most common
        if votes[x["category"]] == top:
            return x
    return labels[0]
