"""Optional uncertainty band from a weather ensemble (ICON-EPS, 40 members).

Each member is traced from the field using the wind at the field. For every
hour, the spread is the 90th percentile distance of the members from their
mean position (at least 1 km).

By default the band is centred on the main smoke path (pass `centre_path`),
and only its width comes from the ensemble. Tested with real forecasts for
Punjab: the ensemble mean (10 m winds, wind at the field only) drifts 30-140 km
away from the refined 120 m path within a day, so a band centred on the mean
would not contain the path it is meant to describe. Without `centre_path` the
centre is the member mean.
"""

import math
from datetime import timedelta

from .trajectory import KM_PER_DEG, STEPS_PER_HOUR, Puff, hourly, single_site, trace

MIN_RADIUS_KM = 1.0
PERCENTILE = 90
MIN_MEMBERS = 2


def percentile(values, q):
    """Linear-interpolated percentile (same as numpy's default)."""
    xs = sorted(values)
    if not xs:
        raise ValueError("percentile of an empty list")
    k = (len(xs) - 1) * q / 100
    lo = math.floor(k)
    hi = math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def trace_members(members, lat, lon, start, hours):
    """One path per member. Members that do not cover the time window are skipped."""
    end = start + timedelta(hours=hours)
    paths = []
    for series in members:
        if not series.covers(start, end):
            continue
        paths.append(trace(single_site(series), lat, lon, start, hours))
    if len(paths) < MIN_MEMBERS:
        raise ValueError("The ensemble forecast does not cover this time")
    return paths


def ensemble_puffs(member_paths, centre_path=None):
    """Hourly puffs. Radius = p90 distance of members from their mean (min 1 km).

    Centre = the hourly point of `centre_path` if given, else the member mean.
    """
    hourly_paths = [hourly(p) for p in member_paths]
    n_hours = min(len(p) for p in hourly_paths)
    centres = hourly(centre_path) if centre_path is not None else None
    if centres is not None:
        n_hours = min(n_hours, len(centres))
    puffs = []
    for h in range(n_hours):
        pts = [p[h] for p in hourly_paths]
        c_lat = sum(p.lat for p in pts) / len(pts)
        c_lon = sum(p.lon for p in pts) / len(pts)
        coslat = math.cos(math.radians(c_lat))
        dists = [
            math.hypot((p.lon - c_lon) * KM_PER_DEG * coslat, (p.lat - c_lat) * KM_PER_DEG)
            for p in pts
        ]
        radius = max(MIN_RADIUS_KM, percentile(dists, PERCENTILE))
        if centres is not None:
            c_lat, c_lon = centres[h].lat, centres[h].lon
        puffs.append(Puff(h, pts[0].t, c_lat, c_lon, radius))
    return puffs


def member_lines(member_paths):
    """Each member path thinned to every 4th point (hourly), as (lat, lon) lists."""
    return [[(p.lat, p.lon) for p in path[::STEPS_PER_HOUR]] for path in member_paths]
