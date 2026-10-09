"""Live air quality at monitoring stations: CPCB's real-time feed on data.gov.in.

The Central Pollution Control Board publishes the latest readings of its ~500 continuous
stations every hour as the data.gov.in resource "Real time Air Quality Index from various
locations". One record per station and pollutant: state, city, station, last_update,
latitude, longitude, pollutant_id (PM2.5, PM10, NO2, SO2, CO, OZONE, NH3) and the min, max and
average value. The average is the one CPCB uses for its AQI (24 h for PM, 8 h for CO and ozone);
CO is in mg/m³, the rest in µg/m³.

Needs a free key (DATA_GOV_IN_API_KEY). Without it, or when data.gov.in is down, the latest
OpenAQ readings are used instead (PM2.5 and PM10 only, often ~2 days late; the age is shown).
"""

import logging
import os
import statistics
import urllib.parse
from datetime import datetime, timedelta

from . import IST, airquality, stations
from .net import ApiError, parse_json, request

log = logging.getLogger(__name__)

RESOURCE_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
PAGE = 1000
MAX_PAGES = 8
TIMEOUT_S = 12
POLLUTANT_IDS = {"PM2.5": "pm2_5", "PM10": "pm10", "NO2": "no2", "SO2": "so2", "CO": "co", "OZONE": "o3", "NH3": "nh3"}
FOCUS_STATES = ("Punjab", "Haryana", "Delhi", "Chandigarh")
FOCUS_BOX = (27.4, 73.8, 32.6, 77.9)  # the same area by location (OpenAQ readings have no state)
INDIA_BOX = (6.5, 68.0, 37.5, 97.5)  # for the OpenAQ fallback


def api_key():
    # API key consumed here: data.gov.in key from the DATA_GOV_IN_API_KEY env var.
    key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    return key or None


def fetch_records(key, timeout=TIMEOUT_S):
    """Every record of the feed (a few thousand), page by page. Raises ApiError."""
    records = []
    for page in range(MAX_PAGES):
        params = {"api-key": key, "format": "json", "limit": PAGE, "offset": page * PAGE}
        url = RESOURCE_URL + "?" + urllib.parse.urlencode(params)
        try:
            raw = request(url, timeout, name="data.gov.in (CPCB)")
        except ApiError as err:
            raise ApiError(str(err).replace(key, "***")) from None
        data = parse_json(raw, "data.gov.in (CPCB)")
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ApiError("data.gov.in (CPCB) sent no records" + (f": {data.get('message')}" if isinstance(data, dict) and data.get("message") else ""))
        batch = data["records"]
        records.extend(batch)
        total = _number(data.get("total"))
        if len(batch) < PAGE or (total is not None and len(records) >= total):
            break
    return records


def _number(x):
    try:
        v = float(str(x).strip())
    except (TypeError, ValueError):
        return None
    return v if v == v and v >= 0 else None


def _when(text):
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(str(text).strip(), fmt).replace(tzinfo=IST)
        except (TypeError, ValueError):
            continue
    return None


def parse_records(records):
    """Records -> stations: [{id, name, city, state, lat, lon, updated, pollutants {p: {avg, min, max}}}]."""
    by_station = {}
    for r in records:
        pid = POLLUTANT_IDS.get(str(r.get("pollutant_id", "")).strip().upper())
        lat, lon = _number(r.get("latitude")), _number(r.get("longitude"))
        name = str(r.get("station") or "").strip()
        if not pid or lat is None or lon is None or not name:
            continue
        avg = _number(r.get("avg_value", r.get("pollutant_avg")))
        s = by_station.setdefault(name, {
            "id": name, "name": name, "city": str(r.get("city") or "").strip(),
            "state": str(r.get("state") or "").strip().replace("_", " "), "lat": lat, "lon": lon,
            "updated": None, "pollutants": {},
        })
        when = _when(r.get("last_update"))
        if when and (s["updated"] is None or when > s["updated"]):
            s["updated"] = when
        if avg is not None:
            s["pollutants"][pid] = {"avg": avg, "min": _number(r.get("min_value", r.get("pollutant_min"))),
                                    "max": _number(r.get("max_value", r.get("pollutant_max")))}
    return list(by_station.values())


def station_aqi(s, min_pollutants=3):
    """CPCB AQI of a station from its averages (CO arrives in mg/m³)."""
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
    """OpenAQ readings in the same shape (PM2.5/PM10 only, as raw hourly values)."""
    rows = stations.fetch_stations(INDIA_BOX, key, now)
    out = []
    for r in rows:
        pol = {}
        for p in ("pm2_5", "pm10"):
            if r.get(p) is not None:
                pol[p] = {"avg": r[p], "min": None, "max": None}
        out.append({"id": f"openaq-{r['id']}", "name": r["name"], "city": city_from_name(r["name"]), "state": "", "lat": r["lat"],
                    "lon": r["lon"], "updated": r["time"], "pollutants": pol})
    return out


def live(now=None):
    """Live station data: CPCB via data.gov.in, else OpenAQ. Returns (doc, cacheable)."""
    now = (now or datetime.now(IST)).astimezone(IST)
    notes = []
    key = api_key()
    if key:
        try:
            found = parse_records(fetch_records(key))
            if found:
                doc = summarise(found, now, "CPCB real-time feed (data.gov.in)")
                doc["notes"] = notes
                return doc, True
            notes.append("data.gov.in sent no station readings.")
        except ApiError as err:
            log.warning("data.gov.in failed: %s", err)
            notes.append(f"CPCB live feed unavailable ({err}).")
    else:
        notes.append("No data.gov.in key (DATA_GOV_IN_API_KEY), so CPCB's live feed is not used.")
    oa_key = stations.api_key()
    if not oa_key:
        raise ApiError("No live station source: add DATA_GOV_IN_API_KEY (or OPENAQ_API_KEY).")
    found = openaq_fallback(oa_key, now)
    doc = summarise(found, now, "OpenAQ (fallback; CPCB readings arrive there about 2 days late)", indicative=True)
    notes.append("Showing OpenAQ readings instead: PM2.5 and PM10 only, and each reading's age is shown. "
                 "AQI from these is indicative (one reading, not CPCB's 24 hour average).")
    doc["notes"] = notes
    return doc, False
