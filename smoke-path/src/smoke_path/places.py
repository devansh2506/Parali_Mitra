"""Villages, towns, schools and hospitals along the smoke path (OpenStreetMap).

One Overpass query uses the hourly path points as a line for the `around`
filter. For every place we find the closest point on the path (checking each
path segment, not just the vertices), interpolate the arrival time there, and
mark it `in_band` if it is within the band radius at that time.
"""

import math
import os
import urllib.parse

from .net import ApiError, parse_json, request
from .trajectory import KM_PER_DEG, flat_km, radius_at

OVERPASS_URL = "https://overpass-api.de/api/interpreter"  # override with the OVERPASS_URL setting
OVERPASS_TIMEOUT_S = 15

TOWN_RADIUS_M = 15000
VILLAGE_RADIUS_M = 5000
AMENITY_RADIUS_M = 3000

SENSITIVE_TYPES = ("school", "college", "hospital", "clinic")
SETTLEMENT_TYPES = ("city", "town", "village")
DEDUPE_KM = 0.5


def _line_coords(line):
    """'lat1,lon1,lat2,lon2,...' with consecutive duplicate points removed."""
    out = []
    for lat, lon in line:
        pair = (round(lat, 5), round(lon, 5))
        if not out or out[-1] != pair:
            out.append(pair)
    return ",".join(f"{lat:.5f},{lon:.5f}" for lat, lon in out)


def build_query(line, server_timeout_s=20):
    """Overpass QL for places near a line of (lat, lon) points."""
    coords = _line_coords(line)
    return (
        f"[out:json][timeout:{int(server_timeout_s)}];\n"
        "(\n"
        f'  node["place"~"^(city|town)$"](around:{TOWN_RADIUS_M},{coords});\n'
        f'  node["place"="village"](around:{VILLAGE_RADIUS_M},{coords});\n'
        f'  nwr["amenity"~"^(school|college|hospital|clinic)$"](around:{AMENITY_RADIUS_M},{coords});\n'
        ");\n"
        "out center tags;"
    )


def overpass_url():
    """Overpass endpoint: the OVERPASS_URL setting, else the main public server."""
    return os.environ.get("OVERPASS_URL", "").strip() or OVERPASS_URL


def fetch_places_raw(line, timeout=OVERPASS_TIMEOUT_S):
    """POST the query to Overpass. Returns raw JSON bytes.

    The server-side limit is 20 s for normal requests; scripts that wait longer
    (save_fixtures.py) let the server work longer too.
    """
    server_timeout = max(20, int(timeout) - 5)
    body = urllib.parse.urlencode({"data": build_query(line, server_timeout)}).encode("utf-8")
    return request(
        overpass_url(),
        timeout,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        name="OpenStreetMap (Overpass)",
    )


def _position(el):
    """(lat, lon) for a node (lat/lon) or a way/relation (center), else None."""
    lat, lon = el.get("lat"), el.get("lon")
    if lat is None or lon is None:
        center = el.get("center") or {}
        lat, lon = center.get("lat"), center.get("lon")
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    return lat, lon


def _place_type(tags):
    place = tags.get("place")
    if place in SETTLEMENT_TYPES:
        return place
    amenity = tags.get("amenity")
    if amenity in SENSITIVE_TYPES:
        return amenity
    return None


def parse_overpass(data):
    """Overpass JSON -> list of places. Elements with no position are skipped."""
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        raise ApiError("OpenStreetMap sent an unexpected reply")
    places = []
    for el in data["elements"]:
        if not isinstance(el, dict):
            continue
        pos = _position(el)
        tags = el.get("tags") or {}
        place_type = _place_type(tags)
        if pos is None or place_type is None:
            continue
        name_en = (tags.get("name:en") or "").strip()
        name_tag = (tags.get("name") or "").strip()
        name = name_en or name_tag
        # Local script name: Punjabi, then Hindi, then `name` when it differs from name:en.
        local = (tags.get("name:pa") or tags.get("name:hi") or (name_tag if name_en else "")).strip()
        places.append(
            {
                "name": name or f"Unnamed {place_type}",
                "name_local": local if local != name else "",
                "place_type": place_type,
                "named": bool(name),
                "lat": pos[0],
                "lon": pos[1],
            }
        )
    return _dedupe(places)


def _dedupe(places):
    """Drop the same named place mapped twice (e.g. a school as a node and a way)."""
    kept = []
    for p in places:
        dup = p["named"] and any(
            k["named"]
            and k["place_type"] == p["place_type"]
            and k["name"].lower() == p["name"].lower()
            and flat_km(k["lat"], k["lon"], p["lat"], p["lon"]) <= DEDUPE_KM
            for k in kept
        )
        if not dup:
            kept.append(p)
    return kept


def _cut_short(data):
    remark = data.get("remark") if isinstance(data, dict) else None
    return bool(remark) and ("error" in remark.lower() or "timed out" in remark.lower())


def decode_places(body):
    """Raw Overpass bytes -> (places, note or None).

    A search that was cut short with nothing found is a failure (ApiError), so
    we never claim "no places" from it. Cut short with some places: keep them
    and add a note.
    """
    data = parse_json(body, "OpenStreetMap (Overpass)")
    found = parse_overpass(data)
    if not _cut_short(data):
        return found, None
    if not data.get("elements"):
        raise ApiError("OpenStreetMap (Overpass) search timed out (server busy)")
    return found, "The list of places may be incomplete (OpenStreetMap search was cut short)."


def closest_point(lat, lon, path):
    """Closest point on the path to (lat, lon), checking every segment.

    Uses a flat projection centred on the place. Returns (distance_km, time).
    On ties the earliest point wins, so a path that loops back gives the first
    arrival.
    """
    coslat = math.cos(math.radians(lat))

    def xy(p):
        return (p.lon - lon) * KM_PER_DEG * coslat, (p.lat - lat) * KM_PER_DEG

    if len(path) == 1:
        x, y = xy(path[0])
        return math.hypot(x, y), path[0].t

    best_d, best_t = math.inf, path[0].t
    ax, ay = xy(path[0])
    for a, b in zip(path, path[1:]):
        bx, by = xy(b)
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        f = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
        d = math.hypot(ax + f * dx, ay + f * dy)
        if d < best_d - 1e-9:
            best_d = d
            best_t = a.t + (b.t - a.t) * f
        ax, ay = bx, by
    return best_d, best_t


def locate(places, path, puffs):
    """Add distance_km, arrival and in_band to each place, sorted by arrival."""
    out = []
    for p in places:
        dist, arrival = closest_point(p["lat"], p["lon"], path)
        band = radius_at(puffs, arrival)
        out.append({**p, "distance_km": dist, "arrival": arrival, "in_band": dist <= band})
    out.sort(key=lambda p: (p["arrival"], p["distance_km"]))
    return out
