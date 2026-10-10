"""A copy of the slow results in S3, shared by every Lambda copy and kept when Lambda restarts.

Without it each new Lambda copy starts empty and the first visitor waits ~25 s while the fires, the wind grid
and the air forecast are fetched again (and Open-Meteo's free daily limit is spent again). With CACHE_BUCKET set,
a copy is written to S3 after each fetch and read back by any copy that has nothing fresh in memory. A scheduled
"warm" call (app.warm) refreshes it, so visitors normally never wait.

Off when CACHE_BUCKET is not set (local runs, tests). Every failure is logged and ignored: the cache may be
missing, it must never break a request.
"""

import gzip
import logging
import os
import re
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)
_client = None


def enabled():
    return bool(os.environ.get("CACHE_BUCKET", "").strip())


def _s3():
    global _client
    if _client is None:
        import boto3  # in the Lambda runtime; only needed when CACHE_BUCKET is set

        _client = boto3.client("s3")
    return _client


def object_name(*parts):
    """A safe S3 key such as cache/wind-120m-2026-10-11-1-3.bin.gz."""
    return "cache/" + re.sub(r"[^A-Za-z0-9._-]+", "-", "-".join(str(p) for p in parts)).strip("-") + ".bin.gz"


def load(name, max_age_s):
    """The bytes saved under `name` if they are younger than max_age_s, else None."""
    if not enabled():
        return None
    try:
        obj = _s3().get_object(Bucket=os.environ["CACHE_BUCKET"], Key=name)
        age = (datetime.now(timezone.utc) - obj["LastModified"]).total_seconds()
        if age > max_age_s:
            return None
        return gzip.decompress(obj["Body"].read())
    except Exception as err:  # noqa: BLE001 - a missing or unreadable copy just means "fetch it again"
        if "NoSuchKey" not in str(err):
            log.warning("shared cache read failed for %s: %s", name, err)
        return None


def save(name, data):
    """Keep `data` (bytes) under `name`."""
    if not enabled():
        return
    try:
        _s3().put_object(Bucket=os.environ["CACHE_BUCKET"], Key=name, Body=gzip.compress(data, compresslevel=6),
                         ContentType="application/octet-stream")
    except Exception as err:  # noqa: BLE001
        log.warning("shared cache write failed for %s: %s", name, err)


def now_s():
    return time.time()
