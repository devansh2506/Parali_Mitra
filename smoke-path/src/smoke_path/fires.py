"""Today's farm fires near the field, from NASA FIRMS (VIIRS satellites).

API: /api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}
The area is LONGITUDE first. `acq_time` is UTC as HHMM. A bad key returns
plain text (or an HTTP error), not CSV, so a reply without a `latitude`
header is treated as an error.
"""

import csv
import io
import os
from datetime import datetime, timezone

from . import IST
from .net import ApiError, request

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/{days}"
SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
FIRMS_TIMEOUT_S = 8
DAY_RANGE = 1
BOX_HALF_DEG = 1.0  # about 1 degree around the field in every direction

CONFIDENCE = {"l": "low", "n": "nominal", "h": "high"}


def map_key():
    """The FIRMS MAP_KEY from the environment, or None."""
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    return key or None


def area(lat, lon, half=BOX_HALF_DEG):
    """'west,south,east,north' around the field (longitude first)."""
    west = max(-180.0, lon - half)
    east = min(180.0, lon + half)
    south = max(-90.0, lat - half)
    north = min(90.0, lat + half)
    return f"{west:.2f},{south:.2f},{east:.2f},{north:.2f}"


def fetch_fires_raw(source, lat, lon, key, timeout=FIRMS_TIMEOUT_S):
    """Raw CSV text for one satellite source, about 1 degree around a field."""
    return _fetch(source, area(lat, lon), key, DAY_RANGE, timeout)


def box_area(box):
    """'west,south,east,north' for a (south, west, north, east) box."""
    south, west, north, east = box
    return f"{west:.2f},{south:.2f},{east:.2f},{north:.2f}"


def fetch_fires_box_raw(source, box, key, days=DAY_RANGE, timeout=FIRMS_TIMEOUT_S):
    """Raw CSV text for one satellite source over a whole region box (south, west, north, east)."""
    return _fetch(source, box_area(box), key, days, timeout)


def _fetch(source, area_text, key, days, timeout):
    """Raises ApiError (never shows the key) unless FIRMS sends fire CSV."""
    url = FIRMS_URL.format(key=key, source=source, area=area_text, days=days)
    try:
        body = request(url, timeout, name=f"NASA FIRMS {source}")
    except ApiError as err:
        raise ApiError(str(err).replace(key, "***")) from None
    text = body.decode("utf-8", errors="replace")
    if not looks_like_firms_csv(text):
        first = " ".join(text.strip().split())[:80].replace(key, "***")
        raise ApiError(f"NASA FIRMS {source} did not send fire data ({first or 'empty reply'})")
    return text


def _header(text):
    text = text.lstrip("﻿")
    first = text.split("\n", 1)[0]
    return [h.strip().lower() for h in first.split(",")]


def looks_like_firms_csv(text):
    return "latitude" in _header(text)


def _float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


SATELLITES = {"VIIRS_SNPP_NRT": "Suomi NPP", "VIIRS_NOAA20_NRT": "NOAA-20", "VIIRS_NOAA21_NRT": "NOAA-21"}
DAYNIGHT = {"D": "day", "N": "night"}


def _fmt_time(t):
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def parse_fires_csv(text, source):
    """FIRMS CSV -> list of fire dicts with every useful column. Returns [] for an error text.

    The time is when the satellite passed over and saw the fire (acq_date +
    acq_time, UTC); the fire may have started earlier.
    """
    if not isinstance(text, str) or not looks_like_firms_csv(text):
        return []
    fires = []
    for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        lat, lon = _float(row.get("latitude")), _float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        date = row.get("acq_date", "")
        hhmm = row.get("acq_time", "").zfill(4)
        time_utc = time_ist = date_ist = seen_at = seen_text = None
        try:
            utc = datetime.strptime(date + hhmm, "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        else:
            ist = utc.astimezone(IST)
            time_utc = utc.strftime("%H:%M")
            time_ist = _fmt_time(ist)
            date_ist = ist.date().isoformat()
            seen_at = ist.isoformat(timespec="minutes")
            seen_text = f"{time_ist}, {ist.day} {ist.strftime('%b')}"
        conf = row.get("confidence", "")
        fires.append(
            {
                "lat": lat,
                "lon": lon,
                "date": date,
                "time_utc": time_utc,
                "time_ist": time_ist,
                "date_ist": date_ist,
                "seen_at": seen_at,
                "seen_text": seen_text,
                "confidence": CONFIDENCE.get(conf.lower(), conf),
                "frp": _float(row.get("frp")),
                "bright_ti4": _float(row.get("bright_ti4")),
                "bright_ti5": _float(row.get("bright_ti5")),
                "scan": _float(row.get("scan")),
                "track": _float(row.get("track")),
                "satellite": SATELLITES.get(source, row.get("satellite") or None),
                "instrument": row.get("instrument") or "VIIRS",
                "daynight": DAYNIGHT.get(row.get("daynight", "").upper(), row.get("daynight") or None),
                "version": row.get("version") or None,
                "source": source,
            }
        )
    return fires
