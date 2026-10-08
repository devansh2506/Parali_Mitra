"""Trace the smoke path along the forecast wind, and the cone-shaped band.

Steps are 15 minutes. Each step is a midpoint (RK2) step: take the wind at
the current point, move half a step, take the wind there, then make the full
step with that second wind. Moves use a flat-earth approximation, which is
fine for steps of a few kilometres.
"""

import math
from collections import namedtuple
from datetime import timedelta

KM_PER_DEG = 111.32
STEP_MINUTES = 15
STEPS_PER_HOUR = 60 // STEP_MINUTES
REFINE_EVERY_HOURS = 3

CONE_START_KM = 1.0
CONE_GROWTH = 0.25  # radius grows 0.25 km per km travelled: about a 14 degree cone each side

PathPoint = namedtuple("PathPoint", "t lat lon km")
Puff = namedtuple("Puff", "hour t lat lon radius_km")


def move(lat, lon, u, v, dt_s):
    """Move (lat, lon) by wind (u east, v north, m/s) for dt_s seconds."""
    dlat = v * dt_s / 1000 / KM_PER_DEG
    coslat = max(math.cos(math.radians(lat)), 0.01)
    dlon = u * dt_s / 1000 / (KM_PER_DEG * coslat)
    return lat + dlat, lon + dlon


def flat_km(lat1, lon1, lat2, lon2):
    """Distance in km using a local flat projection (good for short distances)."""
    coslat = math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * KM_PER_DEG * coslat
    dy = (lat2 - lat1) * KM_PER_DEG
    return math.hypot(dx, dy)


class WindField:
    """Wind from one or more forecast sites. Each lookup uses the nearest site."""

    def __init__(self, sites):
        # sites: list of (lat, lon, WindSeries)
        if not sites:
            raise ValueError("WindField needs at least one site")
        self.sites = list(sites)

    def at(self, t, lat, lon):
        if len(self.sites) == 1:
            return self.sites[0][2].at(t)
        coslat = math.cos(math.radians(lat))
        best = min(
            self.sites,
            key=lambda s: ((s[1] - lon) * coslat) ** 2 + (s[0] - lat) ** 2,
        )
        return best[2].at(t)


def single_site(series):
    """Wind lookup that always uses one series (the wind at the field)."""
    return lambda t, lat, lon: series.at(t)


def trace(wind_at, lat, lon, start, hours, step_minutes=STEP_MINUTES):
    """Follow the wind from (lat, lon) for `hours` hours.

    wind_at(t, lat, lon) -> (u, v) in m/s. Returns a list of PathPoint, one per
    step, starting at the field (km = 0). A time outside the forecast raises
    OutsideForecast (a ValueError).
    """
    dt = step_minutes * 60
    half = timedelta(seconds=dt / 2)
    n_steps = round(hours * 60 / step_minutes)
    points = [PathPoint(start, lat, lon, 0.0)]
    km = 0.0
    t = start
    for i in range(n_steps):
        u1, v1 = wind_at(t, lat, lon)
        mid_lat, mid_lon = move(lat, lon, u1, v1, dt / 2)
        u2, v2 = wind_at(t + half, mid_lat, mid_lon)
        lat, lon = move(lat, lon, u2, v2, dt)
        km += math.hypot(u2, v2) * dt / 1000
        t = start + timedelta(seconds=dt * (i + 1))
        points.append(PathPoint(t, lat, lon, km))
    return points


def hourly(path):
    """Every full-hour point of a 15-minute path (hour 0 is the field)."""
    return path[::STEPS_PER_HOUR]


def refine_sites(path, every_hours=REFINE_EVERY_HOURS):
    """Path points every 3 hours (not the field), used to sample wind along the path."""
    total_hours = (len(path) - 1) // STEPS_PER_HOUR
    marks = list(range(every_hours, total_hours + 1, every_hours)) or [total_hours]
    return [(path[h * STEPS_PER_HOUR].lat, path[h * STEPS_PER_HOUR].lon) for h in marks]


def cone_puffs(path):
    """One puff per hour on the path; radius = 1.0 + 0.25 * km travelled."""
    return [
        Puff(h, p.t, p.lat, p.lon, CONE_START_KM + CONE_GROWTH * p.km)
        for h, p in enumerate(hourly(path))
    ]


def radius_at(puffs, t):
    """Band radius at time t, linearly interpolated between hourly puffs."""
    if t <= puffs[0].t:
        return puffs[0].radius_km
    if t >= puffs[-1].t:
        return puffs[-1].radius_km
    for a, b in zip(puffs, puffs[1:]):
        if a.t <= t <= b.t:
            span = (b.t - a.t).total_seconds()
            f = 0.0 if span <= 0 else (t - a.t).total_seconds() / span
            return a.radius_km + f * (b.radius_km - a.radius_km)
    return puffs[-1].radius_km
