"""What one fire gives off, and how toxic that is.

Burn rate. The satellite measures the fire's radiative power (FRP, MW). Wooster et al. (2005):
0.368 kg of dry vegetation burns per MJ radiated, so a fire burns 0.368 x FRP kg every second
(x 3600 for an hour). This is the rate while the fire burns at the power the satellite saw.

Pollutants. Grams of each pollutant per kg burned, from the GFED4.1 emission factor table
(van der Werf et al. 2017, based mostly on Akagi et al. 2011): "AGRI" (crop residue) for farm
fires and fires in built-up areas, "SAVA" for grassland, "TEMF" for forest. Industrial and
landfill fires are not estimated: these factors are for burning vegetation.

Toxicity score. How much clean air the smoke of one hour would poison up to India's safe limit
(CPCB national standard; WHO guideline where CPCB has none): for each pollutant,
mass / limit = cubic metres of air at exactly the limit, added up and shown in km^3 per hour.
The pollutant with the biggest share is the most harmful one in that smoke.
Total particles (TPM) are shown but not scored, because PM2.5 is part of them.
"""

from . import plume

# g per kg dry matter (GFED4.1). NOx is given as NO.
_FACTORS = {
    "AGRI": {"co2": 1585, "co": 102, "ch4": 5.82, "pm2_5": 6.26, "tpm": 12.4, "oc": 2.3, "bc": 0.75,
             "nox": 3.11, "so2": 0.40, "nh3": 2.17, "benzene": 0.15, "toluene": 0.19, "formaldehyde": 2.08},
    "SAVA": {"co2": 1686, "co": 63, "ch4": 1.94, "pm2_5": 7.17, "tpm": 8.5, "oc": 2.62, "bc": 0.37,
             "nox": 3.9, "so2": 0.48, "nh3": 0.52, "benzene": 0.2, "toluene": 0.08, "formaldehyde": 0.73},
    "TEMF": {"co2": 1647, "co": 88, "ch4": 3.36, "pm2_5": 12.9, "tpm": 17.6, "oc": 9.6, "bc": 0.5,
             "nox": 1.92, "so2": 1.1, "nh3": 0.84, "benzene": 0.27, "toluene": 0.19, "formaldehyde": 2.09},
}
TABLE_FOR = {"farm": "AGRI", "settlement": "AGRI", "grassland": "SAVA", "forest": "TEMF"}
NO2_PER_NO = 46.0 / 30.0

NAMES = {
    "pm2_5": "PM2.5 (fine particles)",
    "tpm": "Total particles (incl. PM10)",
    "bc": "Black carbon (soot)",
    "oc": "Organic carbon",
    "co": "Carbon monoxide (CO)",
    "no2": "Nitrogen oxides (as NO2)",
    "so2": "Sulphur dioxide (SO2)",
    "nh3": "Ammonia (NH3)",
    "benzene": "Benzene",
    "toluene": "Toluene",
    "formaldehyde": "Formaldehyde",
    "ch4": "Methane",
    "co2": "Carbon dioxide (CO2)",
}
ORDER = tuple(NAMES)

# Safe limits in µg/m³: CPCB National Ambient Air Quality Standards 2009 (24 h; CO 8 h;
# benzene annual), formaldehyde WHO 30-minute guideline (CPCB has none).
LIMITS = {"pm2_5": 60, "no2": 80, "so2": 80, "co": 2000, "nh3": 400, "benzene": 5, "formaldehyde": 100}
LIMIT_SOURCE = {"formaldehyde": "WHO"}
LEVELS = ((0.5, "low"), (2.0, "moderate"), (5.0, "high"), (float("inf"), "very high"))


def modelled(category):
    return category in TABLE_FOR


def per_hour_from_burned(burned_kg, category="farm"):
    """kg of each pollutant from burning `burned_kg` of dry vegetation."""
    ef = _FACTORS[TABLE_FOR[category]]
    out = {}
    for k, g_per_kg in ef.items():
        if k == "nox":
            out["no2"] = burned_kg * g_per_kg * NO2_PER_NO / 1000
        else:
            out[k] = burned_kg * g_per_kg / 1000
    return out


def toxicity(kg):
    """{'km3', 'level', 'worst', 'shares'} for kg of pollutants (per hour or in total)."""
    parts = {p: kg[p] * 1e9 / limit / 1e9 for p, limit in LIMITS.items() if kg.get(p)}  # µg / (µg/m³) -> km³
    total = sum(parts.values())
    if total <= 0:
        return None
    worst = max(parts, key=parts.get)
    level = next(name for upper, name in LEVELS if total < upper)
    return {"km3": round(total, 3), "level": level, "worst": worst,
            "shares": {p: round(100 * v / total) for p, v in sorted(parts.items(), key=lambda kv: -kv[1])}}


def from_frp(frp_mw, category):
    """What a fire gives off per hour while burning, or None (no FRP, or not a vegetation fire)."""
    if not frp_mw or frp_mw <= 0 or not modelled(category):
        return None
    burned = plume.COMBUSTION_KG_PER_MJ * frp_mw * 3600
    kg = per_hour_from_burned(burned, category)
    return {"per": "hour", "burned_kg": round(burned), "table": TABLE_FOR[category],
            "kg": {k: _round(kg[k]) for k in ORDER if k in kg}, "toxicity": toxicity(kg)}


def from_field(acres, category="farm"):
    """What burning a whole field gives off (all of it, not per hour)."""
    burned = plume.burned_tonnes(acres) * 1000
    kg = per_hour_from_burned(burned, category)
    return {"per": "field", "burned_kg": round(burned), "table": TABLE_FOR[category],
            "kg": {k: _round(kg[k]) for k in ORDER if k in kg}, "toxicity": toxicity(kg)}


def _round(x):
    return round(x, 2) if x < 10 else round(x, 1) if x < 1000 else round(x)
