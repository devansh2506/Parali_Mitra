"""Build the GeoJSON response and the plain-language summary."""

from datetime import datetime, timedelta

from . import DISCLAIMER, IST, LABEL
from .places import SENSITIVE_TYPES

FARM_ITSELF = timedelta(minutes=15)  # places reached sooner than this are the farm itself
MAX_SUMMARY_PLACES = 3


def fmt_time(t):
    """'2:00 pm' (no leading zero, works on every OS)."""
    t = t.astimezone(IST)
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def fmt_day(t):
    """'9 Oct'. Not %-d, which breaks on Windows."""
    t = t.astimezone(IST)
    return f"{t.day} {t.strftime('%b')}"


def iso(t):
    return t.astimezone(IST).isoformat(timespec="minutes")


def round_5min(t):
    secs = round(t.timestamp() / 300) * 300
    return datetime.fromtimestamp(secs, IST)


def arrival_text(arrival, start):
    """'4:15 pm', rounded to 5 minutes, with the day added if it is not the burn day."""
    r = round_5min(arrival)
    text = fmt_time(r)
    if r.date() != start.astimezone(IST).date():
        text += f" ({fmt_day(r)})"
    return text


def _wording(start, origin):
    """(lead, reach, none, unknown, joiner) for a planned burn or a fire already seen."""
    if origin == "fire":
        lead = f"Smoke from this fire (seen by satellite on {fmt_day(start)} at {fmt_time(start)})"
        return (
            f"{lead} likely travels over:",
            f"{lead} likely does not pass any listed village, school or hospital.",
            f"{lead} likely follows the path on the map "
            "(villages, schools and hospitals could not be checked right now).",
            "at about",
        )
    lead = f"If you burn on {fmt_day(start)} at {fmt_time(start)}"
    return (
        f"{lead}, smoke will likely reach:",
        f"{lead}, the smoke will likely not pass any listed village, school or hospital.",
        f"{lead}, smoke will likely follow the path on the map "
        "(villages, schools and hospitals could not be checked right now).",
        "by about",
    )


def summary(start, located, places_checked=True, origin="field"):
    """Headline, then up to 3 places in the band (schools and hospitals first)."""
    reach, none, unknown, joiner = _wording(start, origin)
    reached = [p for p in located if p["in_band"] and p["arrival"] - start >= FARM_ITSELF]
    sensitive = [p for p in reached if p["place_type"] in SENSITIVE_TYPES]
    others = [p for p in reached if p["place_type"] not in SENSITIVE_TYPES]
    chosen = sorted((sensitive + others)[:MAX_SUMMARY_PLACES], key=lambda p: p["arrival"])
    if not chosen and not places_checked:
        # Places failed or came back incomplete: never claim that no place is affected.
        return [unknown]
    if not chosen:
        return [none]
    lines = [reach]
    for p in chosen:
        label = p["name"] if not p.get("named", True) else f"{p['name']} ({p['place_type']})"
        lines.append(f"{label} {joiner} {arrival_text(p['arrival'], start)}")
    return lines


def _point(lat, lon):
    return {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]}


def _line(points):
    return {
        "type": "LineString",
        "coordinates": [[round(lon, 5), round(lat, 5)] for lat, lon in points],
    }


def _feature(geometry, props):
    return {"type": "Feature", "geometry": geometry, "properties": props}


def build(
    *,
    lat,
    lon,
    start,
    hours,
    path,
    puffs,
    members,
    located,
    fires,
    notes,
    wind_level,
    uncertainty,
    generated_at,
    places_checked=True,
    origin="field",
):
    """Assemble the FeatureCollection. Everything in it is JSON-serialisable."""
    features = [
        _feature(
            _point(lat, lon),
            {
                "kind": "field",
                "origin": origin,
                "start": iso(start),
                "start_text": f"{fmt_day(start)}, {fmt_time(start)}",
            },
        ),
        _feature(
            _line([(p.lat, p.lon) for p in path]),
            {"kind": "path", "km": round(path[-1].km, 1), "hours": hours},
        ),
    ]
    for puff in puffs:
        features.append(
            _feature(
                _point(puff.lat, puff.lon),
                {
                    "kind": "puff",
                    "hour": puff.hour,
                    "time": fmt_time(puff.t),
                    "day": fmt_day(puff.t),
                    "at": iso(puff.t),
                    "radius_km": round(puff.radius_km, 2),
                },
            )
        )
    for line in members:
        features.append(_feature(_line(line), {"kind": "member"}))
    for p in located:
        features.append(
            _feature(
                _point(p["lat"], p["lon"]),
                {
                    "kind": "place",
                    "name": p["name"],
                    "name_local": p["name_local"],
                    "place_type": p["place_type"],
                    "distance_km": round(p["distance_km"], 1),
                    "arrival": iso(p["arrival"]),
                    "arrival_text": arrival_text(p["arrival"], start),
                    "in_band": bool(p["in_band"]),
                },
            )
        )
    for f in fires:
        features.append(
            _feature(
                _point(f["lat"], f["lon"]),
                {"kind": "fire", **{k: v for k, v in f.items() if k not in ("lat", "lon")}},
            )
        )
    return {
        "type": "FeatureCollection",
        "label": LABEL,
        "disclaimer": DISCLAIMER,
        "summary": summary(start, located, places_checked, origin),
        "notes": list(notes),
        "wind_level": wind_level,
        "uncertainty": uncertainty,
        "origin": origin,
        "start": iso(start),
        "hours": hours,
        "generated_at": iso(generated_at),
        "sample": False,
        "features": features,
    }
