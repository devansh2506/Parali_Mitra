"""Serve the Lambda handler and the map on localhost, without Docker or SAM.

    python3.12 scripts/local_server.py              # then open http://127.0.0.1:8000/
    python3.12 scripts/local_server.py --port 9000

GET /smoke?...   -> turned into an API Gateway (HTTP API v2) event for the handler
GET /fires?...   -> fire watch, same handler
GET /air?...     -> 48 hour AQI outlook at one spot, same handler
GET /map.html    -> frontend/map.html (sample data when there is no ?api=)
GET /            -> redirects to /map.html?api=/smoke (live, through this server)

Fires use FIRMS_MAP_KEY from smoke-path/.env (or your shell).
"""

import argparse
import base64
import gzip
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _env import load_env  # noqa: E402

from smoke_path.app import lambda_handler  # noqa: E402

MAP_HTML = ROOT / "frontend" / "map.html"
TEXT = {"Content-Type": "text/plain; charset=utf-8"}


def make_event(method, path, query, headers=None):
    """A minimal API Gateway HTTP API (payload v2) event."""
    params = {}
    for key, value in parse_qsl(query, keep_blank_values=True):
        # API Gateway v2 joins repeated parameters with commas.
        params[key] = f"{params[key]},{value}" if key in params else value
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": query,
        "queryStringParameters": params or None,
        "headers": {str(k).lower(): v for k, v in (headers or {}).items()},
        "requestContext": {"http": {"method": method, "path": path}},
    }


def route(method, target, headers=None):
    """(status, headers, body bytes) for one request. No sockets, so tests can call it."""
    parts = urlsplit(target)
    path = parts.path or "/"
    accepts_gzip = "gzip" in str((headers or {}).get("Accept-Encoding", "")).lower()
    if path in ("/smoke", "/fires", "/air", "/stations", "/forecast"):
        resp = lambda_handler(make_event(method, path, parts.query, headers))
        body = resp["body"]
        data = base64.b64decode(body) if resp.get("isBase64Encoded") else body.encode("utf-8")
        return resp["statusCode"], resp["headers"], data
    if method not in ("GET", "HEAD"):
        return 405, TEXT, b"Method not allowed"
    if path == "/":
        return 302, {"Location": "/map.html?api=/smoke"}, b""
    if path == "/map.html":
        out = {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}
        page = MAP_HTML.read_bytes()
        if accepts_gzip:  # the page carries ~2 MB of sample data
            out.update({"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
            page = gzip.compress(page, compresslevel=6)
        return 200, out, page
    return 404, TEXT, b"Not found"


class Handler(BaseHTTPRequestHandler):
    server_version = "SmokePathLocal/1.0"

    def _serve(self, method):
        try:
            status, headers, body = route(method, self.path, dict(self.headers))
        except Exception:  # noqa: BLE001 - show the error in the terminal, keep serving
            logging.exception("request failed")
            status, headers, body = 500, TEXT, b"Internal error (see terminal)"
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        self._serve("GET")

    def do_HEAD(self):
        self._serve("HEAD")

    def do_OPTIONS(self):
        self._serve("OPTIONS")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_env()  # FIRMS_MAP_KEY etc. from smoke-path/.env (shell variables win)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    base = f"http://{args.host}:{args.port}"
    print(f"Live map:    {base}/            (calls the real APIs through this server)")
    print(f"Sample map:  {base}/map.html    (saved sample data, no API calls)")
    print(f"API:         {base}/smoke?lat=30.245&lon=75.844&hours=24")
    print(f"FIRMS key:   {'set' if os.environ.get('FIRMS_MAP_KEY') else 'NOT set (fires will be skipped)'}")
    print(f"OpenAQ key:  {'set' if os.environ.get('OPENAQ_API_KEY') else 'NOT set (no fallback for the live air tabs)'}")
    print(f"data.gov.in: {'set' if os.environ.get('DATA_GOV_IN_API_KEY') else 'NOT set (live air tabs use OpenAQ instead)'}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
