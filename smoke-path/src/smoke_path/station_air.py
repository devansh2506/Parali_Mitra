"""Measured air quality at monitoring stations, from OpenAQ (stations.py does the fetching).

Turns the latest readings (PM2.5, PM10, NO2, SO2, CO and ozone where a station has them) into the /stations reply:
each station's AQI (Indian AQI, computed in airquality.py), cities and rankings. The readings are often days old;
the age of every reading is shown. CO is in mg/m³ here, the rest in µg/m³.
"""

import logging
import statistics
from datetime import datetime

from . import IST, airquality, stations
from .net import ApiError

log = logging.getLogger(__name__)

FOCUS_STATES = ("Punjab", "Haryana", "Delhi", "Chandigarh", "Rajasthan")
FOCUS_BOX = (24.5, 69.5, 32.6, 78.0)  # the same area by location (OpenAQ readings have no state)
INDIA_BOX = (6.5, 68.0, 37.5, 97.5)  # all of India


def station_aqi(s, min_pollutants=3):
    """Indian AQI of a station from its averages (CO arrives in mg/m³)."""
    conc = {p: v["avg"] * (1000 if p == "co" else 1) for p, v in s["pollutants"].items() if p in airquality.BREAKPOINTS}
    sub = {p: airquality.sub_index(p, c) for p, c in conc.items()}
    return airquality.aqi(conc, min_pollutants), sub


def summarise(found, now, source, indicative=False):
    """The /stations reply: stations with AQI, cities, rankings."""
    out = []
    for s in found:
        result, sub = station_aqi(s, 1 if indicative else 3)
        age = round((now - s["updated"]).total_seconds() / 3600, 1) if s.get("updated") else None
        out.append({
            "id": s["id"], "name": s["name"], "city": s.get("city", ""), "state": s.get("state", ""),
            "lat": round(s["lat"], 5), "lon": round(s["lon"], 5),
            "updated": s["updated"].isoformat(timespec="minutes") if s.get("updated") else None, "age_h": age,
            "aqi": result["aqi"] if result else None,
            "category": result["category"] if result else None,
            "dominant": result["dominant"] if result else None,
            "pollutants": {p: dict(v, sub=sub.get(p)) for p, v in s["pollutants"].items()},
        })
    rated = [s for s in out if s["aqi"] is not None]
    cities = {}
    for s in rated:
        cities.setdefault((s["city"] or s["name"], s["state"]), []).append(s)
    city_rows = []
    for (city, state), group in cities.items():
        value = round(statistics.mean(s["aqi"] for s in group))
        worst = max(group, key=lambda s: s["aqi"])
        city_rows.append({"city": city, "state": state, "aqi": value, "category": airquality.category(value)[0],
                          "stations": len(group), "worst_station": worst["name"], "worst_aqi": worst["aqi"],
                          "dominant": worst["dominant"], "lat": round(statistics.mean(s["lat"] for s in group), 4),
                          "lon": round(statistics.mean(s["lon"] for s in group), 4)})
    city_rows.sort(key=lambda c: -c["aqi"])
    rated.sort(key=lambda s: -s["aqi"])
    s0, w0, n0, e0 = FOCUS_BOX
    focus = [s for s in rated if s["state"] in FOCUS_STATES or (s0 <= s["lat"] <= n0 and w0 <= s["lon"] <= e0)]
    return {
        "source": source,
        "indicative": indicative,
        "generated_at": now.isoformat(timespec="minutes"),
        "stations": out,
        "cities": city_rows,
        "rankings": {
            "most_polluted": [s["id"] for s in rated[:10]],
            "cleanest": [s["id"] for s in rated[::-1][:10]],
            "focus_most_polluted": [s["id"] for s in focus[:10]],
        },
        "counts": {"stations": len(out), "rated": len(rated), "cities": len(city_rows)},
    }


def city_from_name(name):
    """'Vikas Sadan, Gurugram - HSPCB' -> 'Gurugram' (CPCB station names); otherwise the name."""
    base = name.rsplit(" - ", 1)[0]
    return base.rsplit(",", 1)[-1].strip() or name


def openaq_fallback(key, now):
    """OpenAQ readings in the same shape (PM2.5, PM10, NO2, SO2, CO, O3 as single recent readings; CO in mg/m³)."""
    rows = stations.fetch_stations(INDIA_BOX, key, now)
    out = []
    for r in rows:
        pol = {}
        for p in ("pm2_5", "pm10", "no2", "so2", "co", "o3"):
            if r.get(p) is not None:
                pol[p] = {"avg": r[p] / 1000 if p == "co" else r[p], "min": None, "max": None}
        out.append({"id": f"openaq-{r['id']}", "name": r["name"], "city": city_from_name(r["name"]), "state": "", "lat": r["lat"],
                    "lon": r["lon"], "updated": r["time"], "pollutants": pol})
    return out


def live(now=None):
    """Live station data from OpenAQ. Returns (doc, cacheable)."""
    now = (now or datetime.now(IST)).astimezone(IST)
    oa_key = stations.api_key()
    if not oa_key:
        raise ApiError("No live station source: add OPENAQ_API_KEY.")
    found = openaq_fallback(oa_key, now)
    doc = summarise(found, now, "OpenAQ (readings often arrive days late)", indicative=True)
    notes = []
    ages = sorted((now - (r["updated"] if isinstance(r["updated"], datetime) else datetime.fromisoformat(r["updated"]))).total_seconds() / 3600
                  for r in found if r.get("updated"))
    if ages:
        notes.append(f"These OpenAQ readings are {ages[len(ages) // 2]:.0f} hours old (middle value; the oldest is {ages[-1]:.0f} hours).")
    notes.append("Readings: PM2.5, PM10, NO2, SO2, CO and ozone where a station has them (no NH3), each with its age. "
                 "AQI from these is indicative (one reading, not a 24 hour average).")
    doc["notes"] = notes
    return doc, False
