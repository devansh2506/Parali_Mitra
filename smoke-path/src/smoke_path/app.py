"""AWS Lambda handler for GET /smoke (API Gateway HTTP API, payload v2).

GET /smoke?lat=30.245&lon=75.844&start=2026-10-10T14:00&hours=24&uncertainty=cone

Returns a GeoJSON FeatureCollection. 400 for bad input or a start time
outside the forecast, 502 only if the wind forecast itself fails.
"""

import json
import logging
import math
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import IST
from .apis import LiveApi
from .pipeline import SmokeRequest, WindUnavailable, run
from .wind import MAX_FORECAST_DAYS, OutsideForecast, forecast_days_needed, wind_level

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

CACHE_TTL_S = 30 * 60
SAMPLE_PATH = Path(__file__).with_name("sample_response.json")

HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class BadRequest(ValueError):
    """Invalid query parameters (becomes a 400)."""


# ---- request parsing ---------------------------------------------------------


def _number(params, name, lo, hi):
    raw = params.get(name)
    if raw is None or str(raw).strip() == "":
        raise BadRequest(f"{name} is required (decimal degrees).")
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"{name} must be a number in decimal degrees.") from None
    if not math.isfinite(value) or not lo <= value <= hi:
        raise BadRequest(f"{name} must be between {lo} and {hi}.")
    return value


def parse_start(raw, now):
    """Local India time 'YYYY-MM-DDTHH:MM'. Default: the next full hour, IST."""
    if raw is None or str(raw).strip() == "":
        return now.astimezone(IST).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    text = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    raise BadRequest("start must look like 2026-10-10T14:00 (India time).")


def parse_hours(raw):
    if raw is None or str(raw).strip() == "":
        return 24
    try:
        hours = int(str(raw).strip())
    except ValueError:
        raise BadRequest("hours must be a whole number from 1 to 48.") from None
    if not 1 <= hours <= 48:
        raise BadRequest("hours must be a whole number from 1 to 48.")
    return hours


def parse_request(params, now=None):
    now = (now or datetime.now(IST)).astimezone(IST)
    lat = _number(params, "lat", -90, 90)
    lon = _number(params, "lon", -180, 180)
    start = parse_start(params.get("start"), now)
    hours = parse_hours(params.get("hours"))
    uncertainty = str(params.get("uncertainty") or "cone").strip().lower()
    if uncertainty not in ("cone", "ensemble"):
        raise BadRequest("uncertainty must be 'cone' or 'ensemble'.")
    today = now.date()
    if start.date() < today:
        raise BadRequest("The burn time is in the past. The wind forecast starts today (India time).")
    if forecast_days_needed(start + timedelta(hours=hours), today) > MAX_FORECAST_DAYS:
        raise BadRequest(
            f"The burn time plus {hours} hours must fall within the next {MAX_FORECAST_DAYS} days "
            "(the length of the wind forecast)."
        )
    return SmokeRequest(lat=lat, lon=lon, start=start, hours=hours, uncertainty=uncertainty)


def _flag(raw):
    return str(raw or "").strip().lower() in ("1", "true", "yes")


# ---- in-memory cache (warm Lambdas reuse it) -----------------------------------


class ResponseCache:
    def __init__(self, ttl_s=CACHE_TTL_S, max_items=128, clock=time.monotonic):
        self.ttl_s = ttl_s
        self.max_items = max_items
        self._clock = clock
        self._items = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires, value = item
            if self._clock() >= expires:
                del self._items[key]
                return None
            return value

    def put(self, key, value):
        with self._lock:
            now = self._clock()
            for k in [k for k, (exp, _) in self._items.items() if exp <= now]:
                del self._items[k]
            while len(self._items) >= self.max_items:
                del self._items[next(iter(self._items))]  # oldest first
            self._items[key] = (now + self.ttl_s, value)


def cache_key(req, level):
    """lat/lon rounded to 0.01 (about 1 km), start time, hours, band type and wind height."""
    return (round(req.lat, 2), round(req.lon, 2), req.start.isoformat(), req.hours, req.uncertainty, level)


CACHE = ResponseCache()


# ---- responses ------------------------------------------------------------------


def _dump(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def _response(status, body_text):
    return {
        "statusCode": status,
        "headers": dict(HEADERS),
        "body": body_text if body_text is not None else "",
        "isBase64Encoded": False,
    }


def _error(status, message):
    return _response(status, _dump({"error": message}))


_sample_cache = {}


def load_sample_body(path=SAMPLE_PATH):
    """The saved demo response (built by scripts/save_fixtures.py) with sample=true.

    Raises FileNotFoundError if no sample has been saved yet.
    """
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _sample_cache:
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["sample"] = True
        _sample_cache.clear()
        _sample_cache[key] = _dump(doc)
    return _sample_cache[key]


def _method(event):
    http = (event.get("requestContext") or {}).get("http") or {}
    return (http.get("method") or event.get("httpMethod") or "GET").upper()


def handle(event, api=None, cache=None, now=None, sample_path=SAMPLE_PATH):
    """The real handler, with hooks for tests (fake API, own cache, fixed clock)."""
    cache = CACHE if cache is None else cache
    method = _method(event)
    if method == "OPTIONS":
        return _response(204, "")
    if method != "GET":
        return _error(405, "Use GET.")
    params = event.get("queryStringParameters") or {}

    if _flag(params.get("sample")):
        try:
            return _response(200, load_sample_body(sample_path))
        except FileNotFoundError:
            return _error(404, "No sample saved yet. Run scripts/save_fixtures.py first.")

    now = (now or datetime.now(IST)).astimezone(IST)
    try:
        req = parse_request(params, now)
    except BadRequest as err:
        return _error(400, str(err))

    level = wind_level()
    key = cache_key(req, level)
    cached = cache.get(key)
    if cached is not None:
        return _response(200, cached)

    try:
        result = run(req, api or LiveApi.from_env(), level=level, now=now)
    except OutsideForecast as err:
        return _error(400, str(err))
    except WindUnavailable as err:
        return _error(502, f"Wind forecast unavailable: {err}")
    except Exception:  # noqa: BLE001 - log it, never leak internals
        log.exception("smoke path failed")
        return _error(500, "Something went wrong while building the smoke path.")

    body = _dump(result.report)
    if result.cacheable:
        cache.put(key, body)
    return _response(200, body)


def lambda_handler(event, context=None):
    return handle(event)
