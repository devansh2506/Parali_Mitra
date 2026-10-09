"""Fire watch: every fire NASA satellites saw in and around Punjab and Haryana, where its smoke
is likely going, and which villages, schools and hospitals it will reach.

1. NASA FIRMS detections from the three VIIRS satellites in the region, last day.
2. Detections of the same fire (within 1 km and 3 hours of each other) become one fire.
3. ONE Open-Meteo request gives the wind on a 0.75 degree grid (17 x 17 points) around the
   region, including the past hours (the fires were seen earlier).
4. Each fire is traced from the minute it was first seen, with the same 15-minute midpoint
   steps as the smoke path, using wind interpolated from the grid.
5. Saved OpenStreetMap places (snapshot.py) near each path are checked: a place is reached
   if it is inside the cone band (1 km + 0.25 km per km travelled) where the smoke is closest.

A simple wind model, not a smoke dispersion model.
"""

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import DISCLAIMER, IST, LABEL, snapshot
from .apis import FIRE_SOURCES
from .net import ApiError
from .pipeline import WindUnavailable
from .places import SENSITIVE_TYPES
from .report import fmt_day, fmt_time, iso, round_5min
from .trajectory import CONE_GROWTH, CONE_START_KM, KM_PER_DEG, WindGrid, flat_km, hourly, trace
from .wind import OutsideForecast, forecast_days_needed, past_days_needed, wind_level

log = logging.getLogger(__name__)

REGION = "in and around Punjab and Haryana"
FIRE_BOX = (27.6, 73.8, 32.6, 77.6)  # south, west, north, east
GRID = {"south": 24.0, "west": 69.75, "step": 0.75, "rows": 17, "cols": 17}  # 289 wind points
FIRMS_DAYS = 1
CLUSTER_KM = 1.0
CLUSTER_HOURS = 3
MAX_FIRES = 2000
MAX_ARRIVALS_PER_PLACE = 5
TOP_PLACES = 3
BUDGET_S = 25
SHIPPED = object()  # "use the places snapshot shipped with the app"

CONFIDENCE_RANK = {"low": 0, "nominal": 1, "high": 2}
DETAIL_KEYS = (
    "seen_at", "seen_text", "date", "time_utc", "satellite", "instrument", "confidence",
    "frp", "bright_ti4", "bright_ti5", "scan", "track", "daynight", "version", "source",
)


class NoFiresKey(Exception):
    """No NASA FIRMS key is configured (becomes a 503)."""


class FiresUnavailable(Exception):
    """NASA FIRMS failed for every satellite (becomes a 502)."""


@dataclass(frozen=True)
class FireWatchRequest:
    hours: int = 24


@dataclass
class Result:
    report: dict
    cacheable: bool


# ---- 1-2. detections -> fires -------------------------------------------------------


def cluster(detections, km=CLUSTER_KM, hours=CLUSTER_HOURS):
    """Group detections of the same fire (within `km` and `hours`). Returns lists of detections."""
    dets = [d for d in detections if d.get("seen_at")]
    when = [datetime.fromisoformat(d["seen_at"]).timestamp() for d in dets]
    parent = list(range(len(dets)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # Cells at least `km` wide everywhere south of 35 N, so neighbours are in the 3x3 block.
    cell_deg = km / (KM_PER_DEG * math.cos(math.radians(35)))
    cells = {}
    for i, d in enumerate(dets):
        ci, cj = math.floor(d["lat"] / cell_deg), math.floor(d["lon"] / cell_deg)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for j in cells.get((ci + di, cj + dj), ()):
                    if abs(when[i] - when[j]) <= hours * 3600 and flat_km(d["lat"], d["lon"], dets[j]["lat"], dets[j]["lon"]) <= km:
                        parent[root(i)] = root(j)
        cells.setdefault((ci, cj), []).append(i)
    groups = {}
    for i in range(len(dets)):
        groups.setdefault(root(i), []).append(i)
    return [sorted((dets[i] for i in idx), key=lambda d: d["seen_at"]) for idx in groups.values()]


def strength(frp_max):
    """Rough fire strength from the satellite's fire radiative power (MW)."""
    if frp_max is None:
        return None
    return "small" if frp_max < 3 else "medium" if frp_max < 10 else "large"


def summarise(group):
    """One fire from its detections: FRP-weighted position, first time seen, strongest values."""
    weights = [max(d.get("frp") or 0.0, 0.0) for d in group]
    if sum(weights) <= 0:
        weights = [1.0] * len(group)
    total = sum(weights)
    frps = [d["frp"] for d in group if d.get("frp") is not None]
    confs = [d.get("confidence") for d in group if d.get("confidence")]
    first, last = group[0], group[-1]
    frp_max = max(frps) if frps else None
    return {
        "lat": sum(w * d["lat"] for w, d in zip(weights, group)) / total,
        "lon": sum(w * d["lon"] for w, d in zip(weights, group)) / total,
        "seen_at": first["seen_at"],
        "seen_text": first.get("seen_text"),
        "last_seen_at": last["seen_at"],
        "detections": len(group),
        "frp_max": frp_max,
        "frp_sum": round(sum(frps), 2) if frps else None,
        "strength": strength(frp_max),
        "confidence": max(confs, key=lambda c: CONFIDENCE_RANK.get(c, -1)) if confs else None,
        "satellites": sorted({d["satellite"] for d in group if d.get("satellite")}),
        "daynight": first.get("daynight"),
        "details": [
            dict({k: d.get(k) for k in DETAIL_KEYS}, lat=d["lat"], lon=d["lon"]) for d in group[:10]
        ],
    }


# ---- 3-5. wind, paths, places -------------------------------------------------------------


def when_text(t, now):
    """'from about 4:15 pm' (still to come) or 'since about 3:15 am (9 Oct)' (already arrived)."""
    r = round_5min(t)
    text = fmt_time(r)
    if r.astimezone(IST).date() != now.astimezone(IST).date():
        text += f" ({fmt_day(r)})"
    return ("since about " if t <= now else "from about ") + text


def _place_label(p):
    return p["name"] if not p.get("named", True) else f"{p['name']} ({p['place_type']})"


def _plural(n, word, many=None):
    return f"{n} {word if n == 1 else (many or word + 's')}"


def run(req, api, *, level=None, now=None, snap=SHIPPED, budget_s=BUDGET_S, clock=time.monotonic):
    """All fires in the region with their smoke paths and the places they reach.

    snap: the places snapshot (default: the one shipped with the app; None: no places).
    """
    level = level or wind_level()
    now = (now or datetime.now(IST)).astimezone(IST)
    snap = snapshot.get() if snap is SHIPPED else snap
    deadline = clock() + budget_s
    notes = []
    cacheable = True

    if not api.fires_available():
        raise NoFiresKey("Fire watch needs a NASA FIRMS key (FIRMS_MAP_KEY).")

    # 1. Detections from every satellite, in parallel.
    pool = ThreadPoolExecutor(max_workers=len(FIRE_SOURCES))
    try:
        futures = {s: pool.submit(api.fires_box, s, FIRE_BOX, FIRMS_DAYS) for s in FIRE_SOURCES}
        detections, failed = [], []
        for source, future in futures.items():
            try:
                detections.extend(future.result(timeout=max(0.1, deadline - clock())))
            except Exception as err:  # noqa: BLE001 - one satellite may fail (incl. timeouts)
                log.warning("FIRMS %s failed: %r", source, err)
                failed.append((source, err if isinstance(err, ApiError) else "took too long"))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if len(failed) == len(FIRE_SOURCES):
        raise FiresUnavailable(f"NASA FIRMS unavailable: {failed[0][1]}")
    if failed:
        notes.append("Some satellite fire data is missing (" + ", ".join(s for s, _ in failed) + ").")
        cacheable = False

    # 2. One fire per cluster of detections, numbered by the time first seen.
    fires = sorted((summarise(g) for g in cluster(detections)), key=lambda f: (f["seen_at"], f["lat"], f["lon"]))
    if len(fires) > MAX_FIRES:
        notes.append(f"Showing the {MAX_FIRES} strongest of {len(fires)} fires.")
        fires = sorted(fires, key=lambda f: -(f["frp_max"] or 0))[:MAX_FIRES]
        fires.sort(key=lambda f: (f["seen_at"], f["lat"], f["lon"]))
    for n, fire in enumerate(fires, 1):
        fire["id"] = f"F{n}"
        near = snap.nearest(fire["lat"], fire["lon"]) if snap is not None else None
        fire["near"] = near["name"] if near else ""

    reached = {}
    places_checked = snap is not None
    if fires:
        # 3. Wind on the grid, from the first fire's time to the last fire's time + hours.
        starts = [datetime.fromisoformat(f["seen_at"]) for f in fires]
        today = now.date()
        past = past_days_needed(min(starts), today)
        days = max(1, forecast_days_needed(max(starts) + timedelta(hours=req.hours), today))
        points = WindGrid.points(GRID["south"], GRID["west"], GRID["step"], GRID["rows"], GRID["cols"])
        try:
            series = api.forecast(points, days, level, past)
        except ApiError as err:
            raise WindUnavailable(str(err)) from None
        grid = WindGrid(GRID["south"], GRID["west"], GRID["step"], GRID["rows"], GRID["cols"], series)

        # 4-5. Trace every fire and check the saved places along its path.
        untraced = 0
        leaves_saved_area = False
        for fire, start in zip(fires, starts):
            try:
                path = hourly(trace(grid.at, fire["lat"], fire["lon"], start, req.hours))
            except OutsideForecast:
                untraced += 1
                fire["path"] = None
                fire["places_reached"] = None
                continue
            fire["path"] = path
            if snap is None:
                fire["places_reached"] = None
                continue
            line = [(p.lat, p.lon) for p in path]
            if not all(snap.covers(lat, lon) for lat, lon in line):
                leaves_saved_area = True
            count = 0
            for idx, (dist, seg, f) in snap.near_segments(line).items():
                a, b = path[seg], path[min(seg + 1, len(path) - 1)]
                if dist <= CONE_START_KM + CONE_GROWTH * (a.km + (b.km - a.km) * f):
                    reached.setdefault(idx, []).append((a.t + (b.t - a.t) * f, fire["id"]))
                    count += 1
            fire["places_reached"] = count
        if untraced:
            notes.append(f"{_plural(untraced, 'fire')} could not be traced (outside the wind forecast).")
        if snap is None:
            notes.append("Villages, schools and hospitals could not be checked (no saved places).")
        elif leaves_saved_area:
            notes.append("Some smoke paths leave the saved area; places there are not checked here.")
            places_checked = False

    doc = build(fires, reached, snap, req, now, notes, level, places_checked, len(detections))
    return Result(report=doc, cacheable=cacheable)


# ---- report ----------------------------------------------------------------------------------


def _point(lat, lon):
    return {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]}


def _feature(geometry, props):
    return {"type": "Feature", "geometry": geometry, "properties": props}


def build(fires, reached, snap, req, now, notes, level, places_checked, n_detections):
    features = []
    for fire in fires:
        path = fire.get("path")
        props = {k: v for k, v in fire.items() if k not in ("lat", "lon", "path")}
        props.update(kind="fire", traced=path is not None)
        features.append(_feature(_point(fire["lat"], fire["lon"]), props))
        if path:
            features.append(
                _feature(
                    {"type": "LineString", "coordinates": [[round(p.lon, 5), round(p.lat, 5)] for p in path]},
                    {
                        "kind": "fire_path",
                        "fire_id": fire["id"],
                        "times": [iso(p.t) for p in path],
                        "km": [round(p.km, 1) for p in path],
                    },
                )
            )

    places = []
    for idx, arrivals in reached.items():
        arrivals.sort()
        place = snap.place(idx)
        place.update(fires=len(arrivals), first=arrivals[0][0], arrivals=arrivals[:MAX_ARRIVALS_PER_PLACE])
        places.append(place)
    places.sort(key=lambda p: (-p["fires"], p["place_type"] not in SENSITIVE_TYPES, p["first"], p["name"]))
    counts = {}
    for p in places:
        counts[p["place_type"]] = counts.get(p["place_type"], 0) + 1
        features.append(
            _feature(
                _point(p["lat"], p["lon"]),
                {
                    "kind": "reached",
                    "name": p["name"],
                    "name_local": p["name_local"],
                    "place_type": p["place_type"],
                    "fires": p["fires"],
                    "first_arrival": iso(p["first"]),
                    "first_arrival_text": when_text(p["first"], now),
                    "arrivals": [[fid, iso(t)] for t, fid in p["arrivals"]],
                },
            )
        )

    return {
        "type": "FeatureCollection",
        "view": "fires",
        "label": LABEL,
        "disclaimer": DISCLAIMER,
        "region": REGION,
        "fire_box": list(FIRE_BOX),
        "hours": req.hours,
        "summary": summary(fires, places, counts, places_checked, n_detections, now),
        "stats": {"fires": len(fires), "detections": n_detections, "reached": counts},
        "notes": notes,
        "wind_level": level,
        "generated_at": iso(now),
        "places_snapshot": None if snap is None else snap.osm_base,
        "sample": False,
        "features": features,
    }


def summary(fires, places, counts, places_checked, n_detections, now):
    if not fires:
        return [f"No fires were seen by NASA satellites {REGION} in the last day."]
    lines = [
        f"NASA satellites saw {_plural(len(fires), 'fire')} {REGION} in the last day "
        f"({_plural(n_detections, 'satellite detection')})."
    ]
    if not places:
        if places_checked:
            lines.append("Their smoke will likely not pass any listed village, school or hospital.")
        else:
            lines.append("Villages, schools and hospitals on their smoke paths could not be checked right now.")
        return lines
    parts = []
    for types, one, many in (
        (("village",), "village", "villages"),
        (("town", "city"), "town", "towns"),
        (("school", "college"), "school or college", "schools and colleges"),
        (("hospital", "clinic"), "hospital or clinic", "hospitals and clinics"),
    ):
        n = sum(counts.get(t, 0) for t in types)
        if n:
            parts.append(_plural(n, one, many))
    joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    lines.append(f"Their smoke will likely reach {joined}.")
    for p in places[:TOP_PLACES]:
        lines.append(f"{_place_label(p)}: smoke from {_plural(p['fires'], 'fire')}, {when_text(p['first'], now)}.")
    return lines
