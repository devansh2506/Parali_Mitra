"""How much smoke one fire adds at a place on its path (a Gaussian plume along the traced path).

Emission. The satellite measures the fire's radiative power (FRP, MW). Wooster et al. (2005)
found that 0.368 kg of dry vegetation burns per MJ radiated, so a fire burns
0.368 x FRP kg every second. Each kg of burned crop residue gives off the grams of each
pollutant in EMISSION_FACTORS (GFED4.1 table, based mostly on Akagi et al. 2011). A field
fire is assumed to burn at that rate for FIRE_HOURS. For "What if I burn?" the burned mass
comes from the field size instead (STRAW_T_PER_HA, BURNED_FRACTION).

Spread. Downwind distance x and sideways distance y are measured along our traced path.
The plume widens with the Briggs open-country curves for the Pasquill stability class
(from 10 m wind, sunshine and cloud, Turner's method), plus the uncertainty of the path
itself (half the cone band radius). Upward it spreads until it fills the boundary layer
(the mixing height): low mixing heights at night trap smoke near the ground.

    C = Q / (sqrt(2 pi) * u * sigma_y * D) * exp(-y^2 / (2 sigma_y^2))
    D = min(sqrt(pi/2) * sigma_z, mixing height)   (ground-level source, ground reflection)

Not modelled: chemistry (e.g. NO -> NO2 is counted as complete), rain washout, terrain,
and plume rise above the mixing layer. Industrial fires are not modelled at all, because
FRP-to-biomass factors do not apply to kilns or factories.
"""

import math

from .trajectory import CONE_GROWTH, CONE_START_KM

COMBUSTION_KG_PER_MJ = 0.368  # Wooster et al. 2005, J. Geophys. Res. 110, D24311
FIRE_HOURS = 1.0  # assumed burn time of one detected field fire
STRAW_T_PER_HA = 6.3  # Punjab: ~20 Mt paddy straw from ~3.2 Mha of paddy a year
BURNED_FRACTION = 0.8  # share of the straw that actually burns (assumed)
MIN_MIX_M = 100.0  # fire heat lifts smoke at least this high; also the floor for night mixing heights
MIN_WIND_MS = 1.0
MIN_X_M = 100.0

# g per kg dry matter (GFED4.1 emission factors, van der Werf et al. 2017; mostly Akagi et al. 2011).
# NOx is given as NO; we report it as NO2 (x 46/30), i.e. as if all of it turned into NO2.
_AGRI = {"pm2_5": 6.26, "co": 102.0, "nox": 3.11, "so2": 0.40}
EMISSION_FACTORS = {
    "farm": _AGRI,
    "settlement": _AGRI,  # assumed: crop residue and refuse burned at village edges
    "grassland": {"pm2_5": 7.17, "co": 63.0, "nox": 3.9, "so2": 0.48},
    "forest": {"pm2_5": 12.9, "co": 88.0, "nox": 1.92, "so2": 1.1},
}
NO2_PER_NO = 46.0 / 30.0

# Briggs (1973) open-country dispersion: sigma = a * x * (1 + b x)^p, x in m.
SIGMA_Y = {"A": 0.22, "B": 0.16, "C": 0.11, "D": 0.08, "E": 0.06, "F": 0.04}
SIGMA_Z = {
    "A": (0.20, 0.0, 0.0),
    "B": (0.12, 0.0, 0.0),
    "C": (0.08, 0.0002, -0.5),
    "D": (0.06, 0.0015, -0.5),
    "E": (0.03, 0.0003, -1.0),
    "F": (0.016, 0.0003, -1.0),
}


def modelled(category):
    return category in EMISSION_FACTORS


def rates_from_frp(frp_mw, category):
    """Emission rates in g/s for one fire, or None when we do not model this kind of fire."""
    ef = EMISSION_FACTORS.get(category)
    if not ef or not frp_mw or frp_mw <= 0:
        return None
    burn_kg_s = COMBUSTION_KG_PER_MJ * frp_mw
    return _rates(burn_kg_s, ef)


def rates_from_area(acres, hours=FIRE_HOURS, category="farm"):
    """Emission rates in g/s for a field of `acres` burned over `hours`."""
    burned_kg = acres * 0.404686 * STRAW_T_PER_HA * 1000 * BURNED_FRACTION
    return _rates(burned_kg / (hours * 3600), EMISSION_FACTORS[category])


def burned_tonnes(acres):
    return acres * 0.404686 * STRAW_T_PER_HA * BURNED_FRACTION


def _rates(burn_kg_s, ef):
    return {
        "pm2_5": burn_kg_s * ef["pm2_5"],
        "pm10": burn_kg_s * ef["pm2_5"],  # smoke PM2.5 is also PM10 (a lower bound for PM10)
        "co": burn_kg_s * ef["co"],
        "no2": burn_kg_s * ef["nox"] * NO2_PER_NO,
        "so2": burn_kg_s * ef["so2"],
    }


def stability(wind10_ms, radiation_wm2, cloud_pct):
    """Pasquill class A (very unstable) .. F (very stable), Turner's daytime/night table."""
    u = wind10_ms or 0.0
    if radiation_wm2 is not None and radiation_wm2 > 25:  # daytime
        strong, moderate = radiation_wm2 > 600, radiation_wm2 > 300
        if u < 2:
            return "A" if strong or moderate else "B"
        if u < 3:
            return "B" if strong or moderate else "C"
        if u < 5:
            return "B" if strong else "C"
        if u < 6:
            return "C" if strong else "D"
        return "C" if strong else "D"
    cloudy = (cloud_pct or 0) >= 50
    if u < 3:
        return "E" if cloudy else "F"
    if u < 5:
        return "D" if cloudy else "E"
    return "D"


def sigma_y(x_m, cls):
    return SIGMA_Y[cls] * x_m / math.sqrt(1 + 0.0001 * x_m)


def sigma_z(x_m, cls):
    a, b, p = SIGMA_Z[cls]
    return a * x_m * (1 + b * x_m) ** p if b else a * x_m


def concentration(rate_g_s, x_km, y_km, u_ms, mix_m, cls):
    """Ground-level µg/m³ at x km downwind and y km to the side (path uncertainty included)."""
    x = max(x_km * 1000, MIN_X_M)
    band_m = (CONE_START_KM + CONE_GROWTH * x_km) * 1000
    sy = math.hypot(sigma_y(x, cls), band_m / 2)
    depth = min(max(math.sqrt(math.pi / 2) * sigma_z(x, cls), MIN_MIX_M), max(mix_m or MIN_MIX_M, MIN_MIX_M))
    u = max(u_ms or 0.0, MIN_WIND_MS)
    c = rate_g_s / (math.sqrt(2 * math.pi) * u * sy * depth) * math.exp(-((y_km * 1000) ** 2) / (2 * sy * sy))
    return c * 1e6


def along(path, seg, f):
    """(time, km along, transport speed m/s) at fraction f of segment seg of a path."""
    a, b = path[seg], path[min(seg + 1, len(path) - 1)]
    t = a.t + (b.t - a.t) * f
    km = a.km + (b.km - a.km) * f
    dt = (b.t - a.t).total_seconds()
    speed = (b.km - a.km) * 1000 / dt if dt > 0 else 0.0
    return t, km, speed


def nearest(lat, lon, path):
    """(distance km, segment, fraction) of the closest point of a path to (lat, lon)."""
    from .trajectory import KM_PER_DEG

    coslat = math.cos(math.radians(lat))

    def xy(p):
        return (p.lon - lon) * KM_PER_DEG * coslat, (p.lat - lat) * KM_PER_DEG

    if len(path) == 1:
        return math.hypot(*xy(path[0])), 0, 0.0
    best = (math.inf, 0, 0.0)
    ax, ay = xy(path[0])
    for i in range(len(path) - 1):
        bx, by = xy(path[i + 1])
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        f = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
        d = math.hypot(ax + f * dx, ay + f * dy)
        if d < best[0] - 1e-9:
            best = (d, i, f)
        ax, ay = bx, by
    return best


def add_hours(target, t0, start, hours, value):
    """Spread `value` (µg/m³ lasting `hours` from `start`) over whole-hour bins after t0.

    target: {hour index: value}; each bin gets value x the share of that hour covered.
    """
    s = (start - t0).total_seconds() / 3600
    e = s + hours
    h = math.floor(s)
    while h < e:
        overlap = min(e, h + 1) - max(s, h)
        if overlap > 0:
            target[h] = target.get(h, 0.0) + value * overlap
        h += 1
