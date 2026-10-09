"""AWS Lambda handler for GET /smoke, /fires and /air (API Gateway HTTP API, payload v2).

GET /fires?hours=24   Fire watch: every fire NASA saw in and around Punjab and Haryana,
                      what was burning, its smoke path, the villages, schools and hospitals
                      it reaches, and the air quality (India AQI) there.

GET /smoke?lat=30.245&lon=75.844&start=2026-10-10T14:00&hours=24&uncertainty=cone&acres=5
GET /smoke?lat=30.605&lon=74.999&start=2026-10-09T12:37&origin=fire&frp=6.2&fire_type=farm

GET /air?lat=30.9&lon=75.85   48-hour AQI outlook at one spot, with the smoke from the
                              fires in the latest fire watch (JSON, not GeoJSON).

Returns a GeoJSON FeatureCollection. 400 for bad input or a start time
outside the forecast, 502 only if the wind forecast itself fails.
"""

import base64
import gzip
import json
import logging
import math
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import IST, air, firewatch, landuse
from .apis import LiveApi
from .pipeline import SmokeRequest, WindUnavailable, run
from .wind import MAX_FORECAST_DAYS, MAX_PAST_DAYS, OutsideForecast, forecast_days_needed, wind_level

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

CACHE_TTL_S = 30 * 60
GZIP_MIN_BYTES = 50_000  # fire watch replies are often 1-2 MB and shrink about 10x
SAMPLE_PATH = Path(__file__).with_name("sample_response.json")
FIRE_SAMPLE_PATH = Path(__file__).with_name("fire_watch_sample.json")

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
    origin = str(params.get("origin") or "field").strip().lower()
    if origin not in ("field", "fire"):
        raise BadRequest("origin must be 'field' or 'fire'.")
    today = now.date()
    if origin == "fire":
        # A fire already seen by satellite: start = the time it was seen, up to 3 days back.
        if not str(params.get("start") or "").strip():
            raise BadRequest("start is required for a fire: the time the satellite saw it.")
        if start.date() < today - timedelta(days=MAX_PAST_DAYS):
            raise BadRequest(f"The fire time must be within the last {MAX_PAST_DAYS} days.")
    elif start.date() < today:
        raise BadRequest("The burn time is in the past. The wind forecast starts today (India time).")
    if forecast_days_needed(start + timedelta(hours=hours), today) > MAX_FORECAST_DAYS:
        raise BadRequest(
            f"The burn time plus {hours} hours must fall within the next {MAX_FORECAST_DAYS} days "
            "(the length of the wind forecast)."
        )
    acres = _optional(params, "acres", 0.5, 100, 5.0)
    frp = _optional(params, "frp", 0.01, 5000, None)
    fire_type = str(params.get("fire_type") or "farm").strip().lower()
    if fire_type not in landuse.CATEGORIES:
        raise BadRequest("fire_type must be one of: " + ", ".join(landuse.CATEGORIES) + ".")
    return SmokeRequest(lat=lat, lon=lon, start=start, hours=hours, uncertainty=uncertainty, origin=origin,
                        acres=acres, frp=frp, fire_type=fire_type)


def _optional(params, name, lo, hi, default):
    raw = params.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"{name} must be a number.") from None
    if not math.isfinite(value) or not lo <= value <= hi:
        raise BadRequest(f"{name} must be between {lo:g} and {hi:g}.")
    return value


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
    """lat/lon rounded to 0.01 (about 1 km), start time, hours, band type, origin and wind height."""
    return (
        round(req.lat, 2),
        round(req.lon, 2),
        req.start.isoformat(),
        req.hours,
        req.uncertainty,
        req.origin,
        req.acres,
        req.frp,
        req.fire_type,
        level,
    )


CACHE = ResponseCache()


# ---- responses ------------------------------------------------------------------


def _dump(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def _response(status, body_text, gzip_ok=False):
    """API Gateway reply. Large bodies are gzipped (base64) when the client accepts gzip."""
    body_text = body_text if body_text is not None else ""
    headers = dict(HEADERS)
    if gzip_ok and len(body_text) >= GZIP_MIN_BYTES:
        packed = gzip.compress(body_text.encode("utf-8"), compresslevel=6)
        headers.update({"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        return {
            "statusCode": status,
            "headers": headers,
            "body": base64.b64encode(packed).decode("ascii"),
            "isBase64Encoded": True,
        }
    return {"statusCode": status, "headers": headers, "body": body_text, "isBase64Encoded": False}


def _accepts_gzip(event):
    headers = event.get("headers") or {}
    value = next((v for k, v in headers.items() if str(k).lower() == "accept-encoding"), "")
    return "gzip" in str(value).lower()


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


def _path(event):
    http = (event.get("requestContext") or {}).get("http") or {}
    return (event.get("rawPath") or http.get("path") or event.get("path") or "/smoke").rstrip("/")


def handle(event, api=None, cache=None, now=None, sample_path=SAMPLE_PATH, fire_sample_path=FIRE_SAMPLE_PATH):
    """The real handler, with hooks for tests (fake API, own cache, fixed clock)."""
    cache = CACHE if cache is None else cache
    method = _method(event)
    if method == "OPTIONS":
        return _response(204, "")
    if method != "GET":
        return _error(405, "Use GET.")
    params = event.get("queryStringParameters") or {}
    gz = _accepts_gzip(event)
    if _path(event).endswith("/fires"):
        return handle_fires(params, api, cache, now, fire_sample_path, gz)
    if _path(event).endswith("/air"):
        return handle_air(params, api, cache, now, gz)

    if _flag(params.get("sample")):
        try:
            return _response(200, load_sample_body(sample_path), gz)
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
        return _response(200, cached, gz)

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
    return _response(200, body, gz)


def handle_fires(params, api, cache, now, sample_path, gz=False):
    """GET /fires: fire watch for the whole region."""
    if _flag(params.get("sample")):
        try:
            return _response(200, load_sample_body(sample_path), gz)
        except FileNotFoundError:
            return _error(404, "No fire watch sample saved yet. Run scripts/save_fire_watch_sample.py first.")
    try:
        req = firewatch.FireWatchRequest(hours=parse_hours(params.get("hours")))
    except BadRequest as err:
        return _error(400, str(err))
    level = wind_level()
    key = ("fires", req.hours, level)
    cached = cache.get(key)
    if cached is not None:
        return _response(200, cached, gz)
    try:
        result = firewatch.run(req, api or LiveApi.from_env(), level=level, now=now)
    except firewatch.NoFiresKey as err:
        return _error(503, str(err))
    except (firewatch.FiresUnavailable, WindUnavailable) as err:
        return _error(502, str(err) if isinstance(err, firewatch.FiresUnavailable) else f"Wind forecast unavailable: {err}")
    except Exception:  # noqa: BLE001 - log it, never leak internals
        log.exception("fire watch failed")
        return _error(500, "Something went wrong while building the fire watch.")
    body = _dump(result.report)
    if result.cacheable:
        cache.put(key, body)
    return _response(200, body, gz)


def handle_air(params, api, cache, now, gz=False):
    """GET /air: the 48 hour AQI outlook at one spot, with smoke from the latest fire watch."""
    try:
        lat = _number(params, "lat", -90, 90)
        lon = _number(params, "lon", -180, 180)
        hours = parse_hours(params.get("hours"))
    except BadRequest as err:
        return _error(400, str(err))
    level = wind_level()
    key = ("air", round(lat, 2), round(lon, 2), hours, level)
    cached = cache.get(key)
    if cached is not None:
        return _response(200, cached, gz)
    now = (now or datetime.now(IST)).astimezone(IST)
    api = api or LiveApi.from_env()
    notes = []
    known = firewatch.remembered(hours, level)
    if known is None:
        # No recent fire watch in this Lambda: build one (it is cached for /fires too).
        try:
            result = firewatch.run(firewatch.FireWatchRequest(hours=hours), api, level=level, now=now)
            if result.cacheable:
                cache.put(("fires", hours, level), _dump(result.report))
            known = firewatch.remembered(hours, level)
        except Exception as err:  # noqa: BLE001 - fall back to the forecast without fire plumes
            log.warning("fire watch for /air failed: %r", err)
            notes.append("Smoke from today's fires could not be added (the fire watch is unavailable).")
    if known is not None:
        ctx, sources, generated = known
    else:
        try:
            ctx = air.prepare(api, now, firewatch.AIR_GRID, firewatch.MET_GRID)
        except air.AirUnavailable as err:
            return _error(502, f"Air quality forecast unavailable: {err}")
        sources, generated = [], now
    ctx.now = now
    try:
        doc = air_outlook(ctx, sources, lat, lon, generated, notes)
    except Exception:  # noqa: BLE001 - log it, never leak internals
        log.exception("air outlook failed")
        return _error(500, "Something went wrong while predicting the air quality.")
    body = _dump(doc)
    cache.put(key, body)
    return _response(200, body, gz)


def air_outlook(ctx, sources, lat, lon, generated, notes):
    fires = []
    total = {}
    for src in sources:
        extra = ctx.extra(lat, lon, [src])
        pm = extra.get("pm2_5") or {}
        if not pm or max(pm.values()) < 0.5:
            continue
        h = max(pm, key=pm.get)
        fires.append({"id": src.id, "pm2_5_peak": round(pm[h], 1),
                      "at": (ctx.aq.t0 + timedelta(hours=h)).isoformat(timespec="minutes")})
        for p, by_hour in extra.items():
            for k, v in by_hour.items():
                total.setdefault(p, {})[k] = total.get(p, {}).get(k, 0.0) + v
    fires.sort(key=lambda f: -f["pm2_5_peak"])
    outlook = ctx.outlook(lat, lon, total)
    return {
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "generated_at": now_iso(ctx.now),
        "fire_watch_at": now_iso(generated),
        "now": outlook[0] if outlook else None,
        "worst": max(outlook, key=lambda a: a["aqi"]) if outlook else None,
        "outlook": outlook,
        "fires": fires[:10],
        "air": ctx.info(),
        "notes": notes + ctx.notes,
    }


def now_iso(t):
    return t.astimezone(IST).isoformat(timespec="minutes")


def lambda_handler(event, context=None):
    return handle(event)
