"""Tiny HTTP helper on top of urllib (standard library only)."""

import http.client
import json
import threading
import time
import urllib.error
import urllib.request

from . import USER_AGENT


class ApiError(Exception):
    """An external API failed or sent something we cannot use.

    The message is safe to show to users: it never contains a URL or a key.
    """


def _short(text, limit=160):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


STATUS_HINTS = {
    429: "too many requests, try again in a minute",
    500: "server error",
    502: "server error",
    503: "server busy",
    504: "server busy",
}


def _reason_from_body(body):
    """Pull a readable reason out of an error body (JSON or short plain text, never HTML)."""
    text = body.decode("utf-8", errors="replace").strip()
    if text.startswith("<"):
        return ""  # an HTML/XML error page: not useful to show
    try:
        data = json.loads(text)
    except ValueError:
        return _short(text) if text else ""
    if isinstance(data, dict):
        for key in ("reason", "error", "message"):
            if isinstance(data.get(key), str) and data[key].strip():
                return _short(data[key])
        return ""
    return _short(text)


def request(url, timeout, data=None, headers=None, name="API"):
    """GET (or POST when `data` is given) and return the body as bytes.

    Raises ApiError on HTTP errors, timeouts and connection problems.
    """
    all_headers = {"User-Agent": USER_AGENT}
    if headers:
        all_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        try:
            reason = _reason_from_body(err.read())
        except Exception:  # noqa: BLE001 - the body is only a nice-to-have
            reason = ""
        msg = f"{name} answered HTTP {err.code}"
        reason = reason or STATUS_HINTS.get(err.code, "")
        raise ApiError(f"{msg}: {reason}" if reason else msg) from None
    except TimeoutError:
        raise ApiError(f"{name} did not answer within {timeout:g} s") from None
    except urllib.error.URLError as err:
        if isinstance(err.reason, TimeoutError):
            raise ApiError(f"{name} did not answer within {timeout:g} s") from None
        raise ApiError(f"{name} could not be reached ({_short(err.reason, 80)})") from None
    except (OSError, http.client.HTTPException) as err:
        raise ApiError(f"{name} connection failed ({type(err).__name__})") from None


# Open-Meteo refuses too many requests at once from one address ("HTTP 429: Too many concurrent
# requests"), so every Open-Meteo call in this process shares these slots.
OPEN_METEO_SLOTS = threading.BoundedSemaphore(3)
RETRY_429_S = 2.0


def request_open_meteo(url, timeout, name="Open-Meteo"):
    """request() for Open-Meteo: at most 3 at a time, and one retry after a 429."""
    for attempt in (0, 1):
        with OPEN_METEO_SLOTS:
            try:
                return request(url, timeout, name=name)
            except ApiError as err:
                if attempt or "HTTP 429" not in str(err):
                    raise
        time.sleep(RETRY_429_S)


def parse_json(body, name="API"):
    try:
        return json.loads(body)
    except ValueError:
        raise ApiError(f"{name} sent a reply that is not JSON") from None
