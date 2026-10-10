# Parali Mitra: fires and air quality (Feature 6)

The website has two tabs.

**1. Fires.** Every fire NASA satellites saw in India (inside its border outline) in the last day:

* **what was burning:** farm, industrial / brick kiln, landfill, built-up area, forest or grass;
* **its toxicity:** what it gives off per hour while burning (PM2.5, total particles, black carbon,
  CO, NOx, SO2, ammonia, benzene, toluene, formaldehyde, methane, CO2) and a toxicity score;
* **its smoke path:** where the forecast wind takes its smoke in the next 24 hours, and the
  villages, towns, schools and hospitals on that path with arrival times.

All paths are drawn, coloured by toxicity; dots are coloured by what was burning and sized by
toxicity; the table lists every fire, most toxic first.

**2. Air quality**, straight from the APIs (nothing added by us):

* **Now, measured:** the latest readings at monitoring stations (CPCB's live feed on data.gov.in;
  OpenAQ as a fallback), each station's AQI, rankings (most polluted, cleanest, Delhi / Punjab / Haryana /
  Rajasthan) and a city table, for the whole of India.
* **Forecast, next 48 hours:** the CAMS air-quality forecast (ECMWF, via Open-Meteo) as an AQI map
  with a time slider; tap the map for a spot's hourly AQI and pollutants.

The backend is AWS Lambda (Python 3.12, standard library only) + API Gateway HTTP API via AWS SAM,
region ap-south-1. The frontend is one HTML file with Leaflet and OpenStreetMap tiles.

---

## Folder layout

```
smoke-path/
  src/smoke_path/
    app.py          Lambda handler (/smoke and /fires), request checks, 30-minute cache, sample=true
    firewatch.py    fire watch: NASA fires -> merged fires -> smoke paths -> places reached
    pipeline.py     runs one request: 2 wind calls, band, places + fires in parallel
    wind.py         Open-Meteo forecast + ensemble, wind vectors, time interpolation
    trajectory.py   15-minute RK2 path tracing, refine sites, cone band (puffs)
    ensemble.py     optional ensemble band (ICON-EPS members)
    places.py       snapshot-first place lookup, Overpass query, closest point, arrival times
    snapshot.py     the saved copy of OpenStreetMap places (villages, schools, hospitals around Punjab and
                    Haryana; cities and towns for all of India from data/towns_india.json.gz)
    region.py       is a point inside India
    data/places_snapshot.json.gz   that saved copy (made by build_places_snapshot.py)
    fires.py        NASA FIRMS fetch + CSV parsing
    landuse.py      what was burning: land cover, mapped industry, all-year heat sources
    airquality.py   CAMS forecast (Open-Meteo) on a grid, CPCB AQI, weather for spreading smoke
    stations.py     OpenAQ monitoring stations: latest readings (fallback for cpcb.py)
    emissions.py    what a fire gives off per hour and its toxicity score
    air.py          the CAMS forecast grid, a spot's 48 h outlook and the AQI map layer
    cpcb.py         live station readings (CPCB via data.gov.in, OpenAQ fallback), cities, rankings
    data/landcover.bin.gz        ESA WorldCover 2021, ~100 m cells (build_landcover.py)
    data/industry.json.gz        OSM factories, kilns, power plants, landfills (build_industry.py)
    data/static_sources.json.gz  spots burning all year, from NASA's archive (build_static_sources.py)
    report.py       GeoJSON response + summary text
    apis.py         live / recording / saved-fixture access to the APIs
    net.py          tiny urllib helper (timeouts, safe error messages)
    sample_response.json   saved demo response (created by save_fixtures.py)
  tests/            offline unit tests (no network)
  fixtures/         saved real API replies (created by save_fixtures.py)
  scripts/
    try_live.py       calls the real APIs once, prints the summary, saves smoke.geojson
    save_fixtures.py  saves real replies into fixtures/ and rebuilds the sample
    local_server.py   serves the handler + map on localhost, no Docker needed
    build_places_snapshot.py   downloads the places snapshot once (resumable)
    save_fire_watch_sample.py  saves a real fire watch reply as its sample
    build_landcover.py         one-time: ESA WorldCover -> data/landcover.bin.gz (needs rasterio, see below)
    build_industry.py          one-time: OpenStreetMap industry -> data/industry.json.gz
    build_static_sources.py    one-time: a year of NASA VIIRS archive -> data/static_sources.json.gz
  frontend/index.html + css/ js/ data/   the web app (citizen and authority); map.html only redirects to it
  template.yaml      AWS SAM template
```

---

## How the data flows, start to finish (plain English)

### 1. The big picture

The app answers three questions:
1. Where are fires burning right now?
2. Where will their smoke go?
3. How bad is the air, now and for the next 2 days?

Each question has its own data source. The app never creates data. It collects it, does some arithmetic, and draws it.

### 2. Fires

**Where it comes from:** NASA satellites (the "VIIRS" instruments) look for heat from space. NASA publishes every hot spot through a service called FIRMS. We ask it for India's hot spots.

**What we get for each hot spot:**
- exact location
- the time the satellite saw it
- how strong the heat is, called "fire radiative power" (FRP)
- how sure the satellite is that it's a real fire

**Timeline:**
- Satellites pass over a few times a day, and NASA posts each pass about 3 hours later. So a fire is never "live" to the second.
- We ask for the last 2 days, then keep only the last 24 hours. NASA counts whole calendar days, so asking for "1 day" returned nothing.
- Hot spots outside India's border are dropped.
- The server remembers the result for a short while, and the web page also remembers it for a few minutes. This keeps the calls to NASA low.

**Which state and nearest town:** we compare the fire's location against a state-boundary file and a list of towns that ships with the app.

**What was burning:** a satellite only sees heat, not the cause. We guess the cause from the ground under the fire, checking these in order:
1. **A known permanent heat source** such as a kiln or factory. This is only possible around Delhi, Punjab and Haryana, because that's the only place we have factory data.
2. **Industry mapped on OpenStreetMap**, also only in that same area.
3. **Land cover** from the European Space Agency's satellite map, which says whether the ground is farmland, forest, grassland or built-up. We look at it at about 100 m detail in Punjab and Haryana, and about 450 m for the rest of India.

This is why a factory fire in, say, Gujarat shows up as "farm", "built-up" or "unknown". The app says this on the Factory chip with the "*" note. The result is labelled with a reason and a confidence.

### 3. How "toxic" a fire is

This is arithmetic, not machine learning.
1. The fire's heat strength tells us roughly how much plant material is burning per hour. We use a standard science formula: 0.368 kg per megajoule.
2. Each kind of burning (crop, grass, forest) releases known amounts of smoke particles and gases per kilo burned. We use published tables for these.
3. We then ask how much clean air that smoke would spoil per hour. The answer is shown in cubic kilometres of air per hour, then grouped into Low, Moderate, High and Very high.

Factory and landfill fires are not estimated, because those tables don't apply to them. The app shows "Not estimated" for them.

This number is a comparison between fires. It is not a prediction of the air quality at your house.

### 4. Wind

**Where it comes from:** Open-Meteo, a free weather service.

**What we get:** wind speed and direction, on a grid of points about 165 km apart covering all of India. That's roughly 530 points. The data includes both the recent past and the next few days.

**Timeline:** it's refreshed every 6 hours. The free service has daily and per-minute limits, so we fetch the points in chunks and cache them.

### 5. How the smoke path is made

Think of dropping a leaf into a river at the fire and watching where it goes.
1. Start at the fire's location.
2. Look up the wind at that spot and time, blending the nearby grid points.
3. Move the "leaf" in the direction of the wind, for one hour's worth of distance.
4. Repeat hour after hour. Walking backwards in time with the past wind shows where the smoke already went. Walking forward with the forecast shows where it's heading.
5. The result is a line with a timestamp at each step. That's the line you see on the map, with the clock ticks along it.

**Which places the smoke reaches:** we check which places lie within a few kilometres of that line, and note the time the line passes them. This gives "smoke reaches Bisoi at about 9 pm".

Places are listed by type:
- Cities and towns are listed for all of India.
- Villages, schools and hospitals are only listed for the north-west (Punjab and Haryana), because that's the only region where we downloaded them.
- They are listed but not drawn as dots, to keep the map clean.

Honest limit: this is a simple wind-carry line. It doesn't model smoke spreading out, rising, or thinning. It tells you the direction and timing, not how thick the smoke will be.

### 6. Air quality

#### Measured now
- **Source:** the government's CPCB stations, through data.gov.in. If that fails, we fall back to OpenAQ.
- **Caveat 1:** the author's network can't reach the data.gov.in server, so the CPCB route was not tested. The code for it is unverified.
- **Caveat 2:** the OpenAQ readings in the saved sample were about 2–3 days old, and the app says so.
- **What we get per station:** PM2.5, PM10, NO₂, SO₂, ozone and CO (some stations lack some of these).
- **AQI:** we calculate it ourselves with the official Indian formula. Each pollutant gets its own score, and the **worst score is the AQI**. The pollutant that gave it is shown as the "main pollutant". The colours are the official CPCB colours.

#### Forecast for 48 hours
- **Source:** the CAMS atmosphere model (a European air-quality forecast), through Open-Meteo.
- **Detail:** it's a coarse grid, about 165 km apart in our setup. We smooth between the points so the map looks like a gradient rather than squares.
- **Refresh:** every 6 hours.
- **Limits:** it can't see a single village's stubble fire. It sometimes shows very high values when there's desert dust. Bathinda can hit 500 ("Severe"), and we don't cap that.
- **No fire adjustment:** the earlier model that added fire smoke on top was removed. So the forecast and the fires are two separate views.

### 7. Alerts and cases

1. An authority picks a fire, chooses who to warn (farmer, factory owner, municipal body), and edits the English or Hindi message.
2. They can also alert the people on the smoke path.
3. Each fire becomes a **case** with a status (new, warning sent, acknowledged, resolved, dismissed) and a timeline.
4. A citizen sees an alert if it's within about 15 km of their saved home.
5. In **demo mode** all of this is saved in your browser, and the button says "Sent (demo)". Nobody is really contacted, and the demo contacts are obviously fake.
6. In **live mode** it goes to the server's store. On AWS that would be DynamoDB, with optional email by SNS. That's prepared in the template but not deployed.

### 8. How it's shown

- **Demo mode** (the page opened without `?api=`): uses saved samples that ship with the app. It works offline, and the clock is frozen at the time the sample was taken. The badge says "Saved sample".
- **Live mode:** the page asks the server, which fetches fresh data. The badge says "Live". If fires can't be fetched, it falls back to the sample and says so.
- **Map dots:**
  - Fire dot size shows how toxic the fire is.
  - Colour is the toxicity level, or the fire type once you pick a type chip.
  - The chips are one-at-a-time, so you only see the fires that type stands for.
- **Smoke path:** the line with time ticks, animated when you open a fire.
- **Forecast:** the smooth coloured gradient.
- **Citizen home:** nearest station's AQI and pollutants, a 48-hour strip, health advice, and "smoke coming" if a path will pass your home.

### 9. A quick timeline

| Data | How fresh | Refreshed |
|---|---|---|
| Fires | 3 hours behind the satellite pass | every few minutes on screen, about half an hour on the server |
| Wind | recent past plus the next few days | every 6 hours |
| AQI forecast | next 48 hours | every 6 hours |
| Measured AQI | live if CPCB works, otherwise about 2–3 days old (OpenAQ) | every 10 minutes on screen |
| Towns, land cover, states | shipped with the app | only when rebuilt |

### 10. What's real and what isn't

- **Real, computed:** fire locations, wind, the AQI calculation, the path, the toxicity arithmetic.
- **Estimated:** fire type (a guess from the ground) and the toxicity number.
- **Not tested:** the CPCB feed, and anything on AWS (Cognito, DynamoDB, SNS), because none of it is deployed.
- **Demo only:** contacts, "Sent (demo)" alerts, and the 10 Oct sample story (Bisoi and Jharkhand/Odisha fires, because that sample has no Punjab fires).

## How the model works

1. **Wind.** Open-Meteo gives hourly wind speed and direction at 120 m above ground
   (smoke rises; 10 m wind is too low). Direction is where the wind comes **from**, so the
   smoke moves the opposite way: `u = -speed·sin(dir)`, `v = -speed·cos(dir)`.
   We always mix wind as (u, v) vectors, never as angles (350° and 10° must not average to 180°).
2. **Path.** Starting at the field, we move in 15-minute steps. Each step is a midpoint (RK2)
   step: wind here → half step → wind there → full step with that wind.
3. **Refine.** The first path uses wind at the field only. Then we ask Open-Meteo, in **one**
   request, for wind at the field plus points every 3 hours along that path, and trace again using
   the nearest of those points. That is 2 forecast calls in total.
4. **Band.** One circle ("puff") per hour on the path, radius `1 km + 0.25 × km travelled`
   (about 14° each side). Circles are used because night winds make the path loop and stall.
   With `uncertainty=ensemble` the band width comes from 40 ICON-EPS ensemble members instead: each
   hour, radius = 90th percentile distance of the members from their mean position (at least 1 km).
   The band stays centred on the main path (see "Limits" for why); the members are drawn as faint lines.
5. **Places.** Towns within 15 km, villages within 5 km and schools, colleges, hospitals and clinics
   within 3 km of the path, from OpenStreetMap. They come from a **saved copy** shipped with the app
   (`data/places_snapshot.json.gz`, lat 27.5-33, lon 72.5-78.5: Punjab, Haryana, Delhi, north Rajasthan,
   south Himachal, Jammu, east Pakistan Punjab), so the lookup takes milliseconds and cannot fail.
   Only a part of the path that leaves the saved area is sent to the live Overpass API. For each place
   we find the closest point on the path, the time the smoke is there, and whether it is inside the
   band at that time.
6. **Fires.** NASA FIRMS VIIRS detections (S-NPP, NOAA-20, NOAA-21) in about 1° around the field, last day.
   Each fire has the minute the satellite saw it (`acq_date` + `acq_time`, UTC). Tracing a fire
   (`origin=fire`) runs steps 1-5 from the fire's position starting at that time; because that time is
   in the past, the wind request adds Open-Meteo's `past_days` (up to 3 days back).

### Fire watch

1. NASA FIRMS detections from the three VIIRS satellites in the box lat 6-37.5, lon 67-98, kept when
   they are inside India (`data/region.json.gz`, the outline from OpenStreetMap, `scripts/build_region.py`);
   fires in Pakistan, Nepal, Bangladesh and the other neighbours are dropped.
   FIRMS counts whole UTC days, so two days are fetched and only the last 24 hours kept.
2. Detections within 1 km and 3 hours of each other are one fire (several satellites, or several
   pixels of one field). Its position is the FRP-weighted centre; its start time is when it was first seen.
3. ONE Open-Meteo request gives the 120 m wind on a 0.75° grid (17 × 17 points, lat 24-36,
   lon 69.75-81.75), including past hours. Wind between grid points is interpolated.
4. Each fire is traced with the same 15-minute midpoint steps, from the minute it was first seen.
5. A saved place is "reached" if the path passes within its distance (towns 15 km, villages 5 km,
   schools and hospitals 3 km) and it is inside the cone band there (1 km + 0.25 km per km). The map
   checks a tapped spot with the same rule, treating it like a village (5 km).

The overview uses gridded wind, so a fire's overview line can differ a little from its detailed path
("Show this fire's smoke in detail"), which samples the wind along that fire's own path.

### What was burning (fire type)

A VIIRS fire pixel is about 375 m wide, so each detection is judged by what is on the ground within
400 m of it, using three saved files (no API call at run time):

1. **All-year heat sources.** One year of NASA's archived VIIRS data (Suomi NPP + NOAA-20) for the fire
   box. A ~400 m cell counts if NASA marked a detection there as *type 2, static land source*
   (kilns, plants, flares), or if fire was seen there on 3 or more days **outside** the crop-burning
   seasons (wheat: 1 Apr-15 Jun, paddy: 15 Sep-15 Dec). Fields burn once or twice a year in season;
   kilns and factories burn month after month. → **industrial** (high confidence).
2. **Mapped industry.** OpenStreetMap factories (`man_made=works`, `industrial=*`), brick kilns,
   fuel-burning power plants (solar/wind/hydro left out), industrial areas and landfills.
   Inside one, or within 400 m of a mapped point → **industrial** (or **landfill**). In open
   farmland (70%+ cropland) a nearby kiln only lowers the confidence: the field may be what burned.
3. **Land cover.** ESA WorldCover 2021 (10 m, from Sentinel-1/2), saved as the most common class per
   ~100 m cell. 50%+ cropland → **farm fire**; 40%+ built-up → **fire in a built-up area** (waste or
   building); 50%+ trees/shrubs → **forest**; 50%+ grass → **grassland**; otherwise the largest class
   with low confidence.

Detections of one fire are merged; an industrial hit on any of them wins, otherwise the most common type.
On the October 2026 test day: 120 farm fires, 2 industrial, 1 forest, 1 grassland out of 124.

Why not Google Maps: Google has no land-cover API. Its Places API lists businesses, needs a billing
account, and its terms do not allow storing results, so it cannot say "this pixel is a paddy field".

### What a fire gives off (emissions and toxicity)

For every vegetation fire (`emissions` on each fire; `emission.pollutants` in `/smoke`):

* **Burn rate:** the fire's total power in one satellite pass (FRP, MW, all its pixels) × 0.368 kg/MJ
  (Wooster et al. 2005) × 3600 = kg of vegetation burned **per hour** while it burns that hard.
  How long a fire burns is not known, so amounts are per hour.
* **Pollutants:** kg per hour = burned × the GFED4.1 emission factor (van der Werf et al. 2017,
  mostly Akagi et al. 2011): crop residue for farm fires and fires in built-up areas, savanna/grass
  for grassland, temperate forest for forest. PM2.5, total particles (incl. PM10), black carbon,
  organic carbon, CO, NOx (as NO2), SO2, ammonia, benzene, toluene, formaldehyde, methane, CO2.
  Industrial and landfill fires are not estimated (the factors are for burning vegetation).
* **Toxicity score:** for each pollutant with a health limit, kg ÷ limit = the air it would poison up
  to that limit (PM2.5 60, NO2 80, SO2 80, CO 2000, NH3 400, benzene 5 µg/m³: CPCB national standards;
  formaldehyde 100 µg/m³: WHO), added up, in km³ of air per hour. Low < 0.5, moderate < 2, high < 5,
  very high ≥ 5. The share of each pollutant shows which one is most harmful (usually PM2.5, then NO2).
  Total particles are not scored (PM2.5 is part of them).

Example: a 5 MW farm fire burns ~6.6 t of straw an hour and gives off ~41 kg PM2.5, ~680 kg CO,
~32 kg NOx (as NO2), ~1 kg benzene: about 1.8 km³ of air poisoned per hour (moderate).

### Air quality

**Forecast (CAMS).** Open-Meteo serves the CAMS global forecast free and without a key: PM2.5, PM10,
CO, NO2, SO2, ozone and dust, hourly, 0.4° (~45 km). We fetch it for all of India on a 1.5° (~165 km) grid of 22 × 22 points (lat 6-37.5,
lon 67.2-98.7; Open-Meteo counts each point as a call: 600 a minute, 10,000 a day) from one day back to three days
ahead, in 3 parallel requests, and reuse it for 6 hours.
Nothing is added or corrected: the values are CAMS's own.

**Measured (stations).** CPCB's real-time feed on data.gov.in (about 500 stations, hourly, all
pollutants, each with CPCB's own averages). Without a data.gov.in key, or when it is down, OpenAQ is
used instead: PM2.5, PM10, NO2, SO2, CO and ozone (no NH3), often ~2 days late, so the AQI is marked indicative and every
reading shows its age.

**India's AQI (CPCB).** Each pollutant gets a sub-index from CPCB's breakpoints (24 hour averages for
PM2.5, PM10, NO2, SO2 and ammonia; the highest 8 hour average of the last 24 hours for CO and ozone);
the AQI is the highest sub-index (at least 3 pollutants incl. PM2.5 or PM10), with CPCB's category,
colour and health advice. A city's AQI is the average of its stations'.

## Run the tests (no network needed)

```bash
cd smoke-path
python3.12 -m unittest discover -s tests -v
```

---

## Your keys (FIRMS for fires, OpenAQ for stations)

Put them in `smoke-path/.env` (copy `.env.example`); the scripts read it automatically and git ignores it:

```
FIRMS_MAP_KEY=<YOUR_FIRMS_MAP_KEY>
OPENAQ_API_KEY=<YOUR_OPENAQ_API_KEY>
```

The OpenAQ key is free: sign up at https://explore.openaq.org/register, then copy the key from your
account settings. It is the fallback for the measured air tab when data.gov.in is unavailable.

```
DATA_GOV_IN_API_KEY=<YOUR_DATA_GOV_IN_KEY>
```

The data.gov.in key (free: data.gov.in → My Account → Generate API Key) gives CPCB's live station feed.

## Try it with real data

```bash
cd smoke-path
python3.12 scripts/try_live.py 30.245 75.844                     # next full hour, 24 h
python3.12 scripts/try_live.py 30.245 75.844 2026-10-10T14:00 48 --ensemble
python3.12 scripts/try_live.py 30.60486 74.99966 2026-10-09T12:37 24 --fire   # a fire seen by satellite
```

It prints the summary, notes, path length, places in the band, fire count and how long it took,
and writes `smoke.geojson` (drag it onto https://geojson.io to look at it).

## Save real sample data (for the demo and for `sample=true`)

```bash
python3.12 scripts/save_fixtures.py             # demo field 30.245, 75.844, tomorrow 2 pm, 24 h
python3.12 scripts/save_fixtures.py --fires-only  # refresh only today's fires (keeps path + places)
python3.12 scripts/save_fixtures.py --offline     # rebuild the sample from saved replies only
```

A new capture never makes the sample worse: if OpenStreetMap is busy and the new list of places
comes back incomplete, the previous wind + places are kept and only the fires are updated.

This saves the raw replies in `fixtures/`, rebuilds the demo response from them (no network),
and copies it to `src/smoke_path/sample_response.json` and into `frontend/map.html`.
If an API is down during the demo, `?sample=true` (or the map without `?api=`) still works.

## The saved places (Option B)

The public Overpass server is often overloaded (on 9 Oct 2026 it failed in almost every live run), and
villages do not move, so places are downloaded once and shipped with the Lambda:

```bash
python3.12 scripts/build_places_snapshot.py               # downloads 132 tiles of 0.5°, resumable
python3.12 scripts/build_places_snapshot.py --build-only  # rebuild the file from .snapshot_cache/
```

It fetches tiles nearest Punjab first, waits and retries when the server is busy (fetching a heavy tile
as 4 quarters), and keeps finished tiles in `.snapshot_cache/` (git-ignored), so you can stop it and
run it again to continue. Tiles that never finish are left out; paths that reach them use live Overpass
(the farmer view, with an 8 s limit) or say "not checked here" (fire watch).

**What is saved now (9 Oct 2026):** 61 of the 132 tiles, 25,703 places (15,896 villages, 2,034 schools,
548 colleges, 4,913 hospitals, 1,886 clinics, 362 towns, 64 cities): all of Punjab and most of Haryana,
including Chandigarh, Karnal, Kurukshetra, Panipat, Hisar and Sirsa, plus the border area of Pakistan
Punjab. Not yet saved: Rohtak, Delhi and the outer ring. Checked against a live Overpass answer for one
24-hour path: 500 of the 501 places in the saved tiles matched, none extra (the one difference was a
village 5.008 km from the path, right at the 5 km limit). To add the rest later, run the script again.

The main Overpass server allows about 10 minutes of query time per day per user; if it refuses you
(HTTP 429 or "connection refused"), wait a day or use the VK Maps mirror:
`OVERPASS_URL=https://maps.mail.ru/osm/tools/overpass/api/interpreter python3.12 scripts/build_places_snapshot.py`

## Rebuild the fire-type data (one time, optional)

The three files in `src/smoke_path/data/` are already built. To rebuild them:

```bash
python3.12 -m venv .venv-build && .venv-build/bin/pip install rasterio numpy   # only for land cover
.venv-build/bin/python scripts/build_landcover.py     # ESA WorldCover tiles from AWS, ~5 minutes
python3.12 scripts/build_industry.py                  # OpenStreetMap via Overpass (OVERPASS_URL to pick a mirror)
python3.12 scripts/build_static_sources.py            # one year of NASA VIIRS archive (FIRMS key), ~150 requests
```

The app itself never needs rasterio or numpy.

## Fire watch sample

```bash
python3.12 scripts/save_fire_watch_sample.py
```

Saves a real fire watch reply (`fixtures/fire_watch_sample.json`, the Lambda copy, and the map),
used by `/fires?sample=true` and by the map when it has no `?api=`.

## Run locally (no Docker)

```bash
python3.12 scripts/local_server.py
```

* http://127.0.0.1:8000/ is the live map (fire watch first; calls the real APIs through the local server).
* http://127.0.0.1:8000/index.html is the saved sample, with no API calls.
* http://127.0.0.1:8000/smoke?lat=30.245&lon=75.844&hours=24 is the raw GeoJSON.

---

## Deploy to AWS

```bash
cd smoke-path
sam validate --lint
sam build
sam deploy --guided --region ap-south-1
```

`sam deploy --guided` asks:

| Prompt | Answer |
| --- | --- |
| Stack Name | `parali-mitra-smoke-path` |
| AWS Region | `ap-south-1` |
| Parameter FirmsMapKey | paste your FIRMS MAP_KEY (it is hidden; leave empty to skip fires) |
| Parameter DataGovInApiKey | paste your data.gov.in key (hidden) |
| Parameter OpenAqApiKey | paste your OpenAQ key (hidden; fallback for measured air) |
| Parameter WindLevel | press Enter (`120m`) |
| Parameter OverpassUrl | press Enter (main Overpass server) |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `y` |
| Disable rollback | `n` |
| SmokePathFunction may not have authorization defined, Is this okay? | `y` (it is a public, read-only demo API) |
| Save arguments to configuration file | `y` |
| SAM configuration file / environment | press Enter for both |

At the end SAM prints **SmokeApiUrl**, for example
`https://abc123.execute-api.ap-south-1.amazonaws.com/smoke`. Open the map with
`frontend/map.html?api=<SmokeApiUrl>`.

Later deploys are just `sam build && sam deploy`. To remove everything: `sam delete`.

---

## API

### `GET /fires?hours=24` (fire watch)

`hours` is 1-48 (default 24); `sample=true` returns the saved sample. The reply is a GeoJSON
FeatureCollection with `kind` = `fire` (one per merged fire: `id`, `seen_at`, `seen_text`,
`detections`, `frp_max`, `strength`, `satellites`, `confidence`, `near`, `places_reached`, `traced`,
`details` with every detection, `frp_mw`, and what was burning: `fire_type`
(`farm|industrial|waste|settlement|forest|grassland|unknown`), `fire_type_label`, `fire_type_detail`,
`fire_type_confidence`, `fire_type_reason`, `land_cover` (% by class), `emissions` (kg per hour of each
pollutant and `toxicity`; null when not estimated)), `fire_path` (hourly line with `times` and `km`), `reached`
(`name`, `name_local`, `place_type`, `near_town` (nearest town within 25 km, to tell apart villages with
the same name), `fires`, `first_arrival`, `arrivals` = up to 5 `[fire id, time]`),
Top level: `summary`, `stats` (incl. `fire_types`), `notes`, `generated_at`, `region`.
Errors: 503 without a FIRMS key, 502 if NASA FIRMS or the wind forecast fails.
Replies over 50 KB are gzipped when the client sends `Accept-Encoding: gzip` (browsers always do);
a busy day's fire watch is 1-2 MB raw and about 0.2 MB gzipped.

### `GET /air?lat=30.9&lon=75.85` (forecast at one spot)

The CAMS forecast at a spot, hourly for 48 hours, as India's AQI. JSON: `now`, `worst`, `outlook`
(each `{t, aqi, category, dominant, pm2_5, pm2_5_24h, pm10, co (mg/m³), no2, so2, o3, dust, cigarettes}`),
`inside_region`. Cached 30 minutes per ~1 km.

### `GET /forecast` (forecast map)

AQI on the CAMS grid every 3 hours for 48 hours: `south`, `west`, `step`, `rows`, `cols`, `times`,
`aqi[time][node]`. Cached 30 minutes.

### `GET /stations` (live air at monitoring stations)

Latest readings and the CPCB AQI at every monitoring station, from CPCB's real-time feed on
data.gov.in (needs `DATA_GOV_IN_API_KEY`: free, data.gov.in → My Account → Generate API Key). Without
the key, or when data.gov.in is down, OpenAQ readings are used instead (PM2.5, PM10, NO2, SO2, CO, ozone; no NH3; often ~2 days
late, AQI marked indicative). JSON: `source`, `stations` (name, city, state, lat, lon, updated, age_h,
aqi, category, dominant, pollutants with avg/min/max/sub-index), `cities` (average AQI of a city's
stations, worst station), `rankings` (most polluted, cleanest, most polluted in Delhi/Punjab/Haryana/Rajasthan),
`notes`. Cached 30 minutes. Used by the "Live air" tabs.

### `GET /smoke` (one smoke path)

`GET /smoke?lat=30.245&lon=75.844&start=2026-10-10T14:00&hours=24&uncertainty=cone`

| Parameter | Meaning |
| --- | --- |
| `lat`, `lon` | required, decimal degrees |
| `start` | optional, India time `YYYY-MM-DDTHH:MM`; default the next full hour |
| `hours` | optional, 1 to 48, default 24 |
| `uncertainty` | optional, `cone` (default) or `ensemble` |
| `origin` | optional, `field` (default: a planned burn, `start` today or later) or `fire` (a fire already seen by satellite: `start` = the time it was seen, required, up to 3 days back) |
| `acres` | optional, field size for a planned burn, 0.5 to 100, default 5 |
| `frp`, `fire_type` | optional, for `origin=fire`: the fire's power in MW and what was burning (default `farm`) |
| `sample=true` | returns the saved demo response, with `"sample": true`, no external calls |

The reply is a GeoJSON FeatureCollection. Every feature has `properties.kind`:
`field`, `path` (with `km`), `puff` (one per hour: `hour`, `time`, `radius_km`),
`member` (ensemble only), `place` (`name`, `name_local`, `place_type`, `distance_km`, `arrival`,
`arrival_text`, `in_band`, `air` for places in the band) and `fire` (`date`, `time_utc`, `time_ist`, `date_ist`, `seen_at`, `seen_text`,
`confidence`, `frp`, `bright_ti4`, `bright_ti5`, `scan`, `track`, `satellite`, `instrument`, `daynight`,
`version`, `source`).
Top level: `label`, `summary` (headline, one line per place, then how much the fire releases and the
place that gets the most), `emission` (acres, straw burned, PM2.5 kg, rates), `air`, `notes` (warnings),
`wind_level`, `uncertainty`, `origin`, `sample`.

Errors: **400** `{"error": "..."}` for bad input or a time outside the forecast; **502** only when the
wind forecast itself fails. If places or fires fail, the reply is still **200** with a note.

Settings (Lambda environment variables): `FIRMS_MAP_KEY` (from the `FirmsMapKey` parameter),
`OPENAQ_API_KEY` (from `OpenAqApiKey`),
`WIND_LEVEL` (`10m`, `80m`, `120m` or `180m`, default `120m`) and `OVERPASS_URL` (default
`https://overpass-api.de/api/interpreter`).

---

## Limits of the model (please read)

* The path only **follows the wind** at one height (120 m). It does not model how smoke spreads,
  settles or reacts, and it does not say how much smoke arrives. It is not a dispersion model.
* What a fire gives off is per hour at the power the satellite saw; how long it burns is not known.
  Industrial fires are not estimated (the factors are for burning vegetation).
* The forecast is CAMS's (~45 km cells, so it cannot see one village next to one field). CAMS
  sometimes forecasts strong desert dust over Punjab, Haryana and Rajasthan; the page says so.
* Measured values come from CPCB stations; through OpenAQ they are often ~2 days late (shown).
* Fire type: land cover is from 2021 and judged within 400 m; OpenStreetMap misses many brick kilns;
  a field next to a kiln can be labelled either way (the confidence says so).
* It uses one height (120 m). Real smoke spreads across many heights with different winds.
* Wind forecasts have errors, and they grow with time. Night-time calm winds are the hardest.
  That is why the band widens and why it says "likely".
* The cone band is a fixed rule (about 14° each side), not a measured uncertainty. The ensemble band
  width is measured from the forecast spread, but ICON-EPS only has 10 m winds (its 80/100/120 m values
  are empty), which are slower than 120 m winds, so the spread is probably too narrow.
* In ensemble mode the band is centred on the main path, not on the ensemble mean. Checked with real
  forecasts for Sangrur (10 Oct 2026): the ensemble mean drifted 30 to 140 km from the 120 m path within
  48 hours, and the path stayed inside a mean-centred band for only 3 of 48 hours (GFS 120 m: 6 of 48;
  ECMWF 100 m: 24 of 48). A band that does not contain its own path would confuse farmers, so only
  the width comes from the ensemble.
* "In band" uses the distance from the place to the path and the band radius at the arrival time.
* Places come from a saved OpenStreetMap copy (see "The saved places"), so new villages or schools added
  to OpenStreetMap after the download are missing until it is rebuilt. Outside the saved area the live
  Overpass server is used; it is sometimes overloaded, and then the reply still comes back with a note
  and the summary never claims that no place is affected. Set `OverpassUrl` to another Overpass server
  if the main one stays down.
* Places come from OpenStreetMap, which is incomplete in rural areas; a missing school is not a safe school.
* Fires are satellite detections from the last day. Clouds hide fires, and small fires can be missed.
* A fire's time is when the satellite passed over (VIIRS passes Punjab around 1:30 am and 1:30 pm), not
  when the fire was lit. Tracing from that time shows where its smoke went from then on.

## Data sources and terms

* Wind: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0, free for non-commercial use).
* Places: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, via the
  [Overpass API](https://overpass-api.de/). The saved copy in `src/smoke_path/data/` and the replies in
  `fixtures/` are OpenStreetMap data, available under the
  [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
* Fires: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) VIIRS active fire data (free MAP_KEY), and its
  standard-processing archive for the all-year heat sources.
* Air quality: [Copernicus Atmosphere Monitoring Service](https://atmosphere.copernicus.eu/) (CAMS) global
  forecast via the [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api);
  stations via [OpenAQ](https://openaq.org/) (CPCB and other reference monitors).
* Land cover: [ESA WorldCover 2021 v200](https://esa-worldcover.org/), © ESA WorldCover project /
  Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium, CC BY 4.0.
* Emission factors: GFED4.1 table (van der Werf et al. 2017; Akagi et al. 2011); combustion rate:
  Wooster et al. 2005; AQI: CPCB National Air Quality Index.
* Map tiles: OpenStreetMap (attribution shown on the map).

## Where data covers what

| Data | Area |
|---|---|
| Measured air quality (CPCB / OpenAQ), forecast map | all of India |
| Fires, what was burning, toxicity, smoke paths | all of India (wind on a 1.5° grid, 529 points) |
| Land cover for "what was burning" | 100 m around Punjab and Haryana, 450 m for all of India (`landcover_india.bin.gz`, `build_landcover.py --national`) |
| Factories, kilns, all-year heat sources | Punjab and Haryana only (the all-India versions were not built); elsewhere a fire is labelled from land cover alone, so industrial fires there show as farm, built-up or unknown. The report carries `industry_box`, and the app marks the Factory or kiln chip with * and says so |
| Villages, schools, hospitals on a smoke path | around Punjab and Haryana; cities and towns elsewhere |

## The web app: two roles

Open `frontend/index.html` (a plain static site: no build step, no framework; Leaflet from cdnjs).

| Role | What they see | What they can do |
|---|---|---|
| **Citizen** | My area (air now, next 48 h, smoke coming, health advice), calm map, air forecast, alerts inbox, health tips. English and Hindi. | Read only. |
| **Authority** | Dashboard (KPIs, fire queue, map), fire detail with animated smoke path, fires table, cases board, alerts sent, air quality. | Warn the source of a fire, alert the people on its smoke path, track each fire as a case (new, warning sent, acknowledged, resolved or dismissed, with a timeline). |

**Demo mode (default).** No `?api=`: the app uses saved samples (`frontend/data/sample-*.js`, made by
`scripts/save_frontend_samples.py`) and keeps alerts and cases in this browser (`localStorage`). Every action says
"(demo)". It works with no server and no internet except map tiles and fonts. The login is a demo login: no password,
not secure. "Demo: switch role" in the account menu swaps citizen and authority in one click.

**Live mode.** `index.html?api=/` through `scripts/local_server.py` (or `?api=https://<your API>` on AWS). Fires, air and
alerts come from the server; alerts and cases are kept by the server (memory locally, DynamoDB on AWS).

**What is demo and what is real**
* Real: fires, smoke paths, toxicity, what was burning, air quality (OpenAQ now; CPCB when the feed is reachable), forecast.
* Demo: the login, the contact registry (made-up names, `+91-00000-…` numbers, `@example.com` addresses), sample data.
* Not connected: owner lookup from land records or factory licences. A real contact has to be typed in.
* Not verified: the CPCB feed parsing (the data.gov.in server refuses connections from my network), Cognito sign-in
  against a real user pool, SNS email, DynamoDB on AWS (the store is tested with a fake table).
* Delivery: the in-app inbox is the main channel. SMS in India needs DLT registration, so it is not used.
* Map tiles: Esri "Canvas" light and dark (no key); CARTO now asks for a key. OpenStreetMap is the fallback.
* Population is not shown (we have no population data): the dashboard counts places, not people.

### New endpoints

| Call | Who | What |
|---|---|---|
| `POST /alerts` | authority | `{fire_id, kind: source_warning or public_alert, target, message, language, fire}`; saves it, updates the case |
| `GET /alerts?lat&lon&radius_km` | anyone | public alerts with a place near that spot (the citizen inbox); never returns warnings to sources |
| `GET /activity` | authority | every alert sent |
| `GET /cases`, `PATCH /cases/{fire_id}` | authority | the cases; set status (`new`, `warning_sent`, `acknowledged`, `resolved`, `dismissed`) or add a note |

Each fire has a stable `key` (spot + day first seen, e.g. `30.20_75.80_20261010`) and a `state`; the key is the case id.

### Deploy it yourself (I never run these)

Nothing here has been deployed. With the defaults (`EnableAuth=false`) the authority routes are **open**: anyone with the
API address could send alerts. Use that only for a private demo.

1. Build and deploy (replace the placeholders; keys are asked for as hidden parameters):
   ```
   cd smoke-path
   sam build
   sam deploy --guided --stack-name parali-mitra --region ap-south-1
   ```
   At the prompts give `FirmsMapKey`, `DataGovInApiKey`, `OpenAqApiKey` (`<YOUR_KEY_HERE>`), leave `EnableAuth` as `false` first.
2. Note `ApiBaseUrl` from the outputs. Open the app with `index.html?api=<ApiBaseUrl>`.
3. Host the app (optional): create a bucket and a CloudFront distribution for the `frontend/` folder, then
   `aws s3 sync frontend/ s3://<YOUR_BUCKET>/ --delete`.
4. Turn on sign-in with Amazon Cognito:
   ```
   sam deploy --parameter-overrides EnableAuth=true CognitoDomainPrefix=<unique-word> AppUrl=https://<your app address>/index.html
   ```
   Then put `domain` (output `CognitoDomain`) and `clientId` (output `UserPoolClientId`) in the `cognito` block of
   `frontend/index.html` and open the app with `?auth=cognito`. Create people and add officers to the group:
   ```
   aws cognito-idp admin-create-user --user-pool-id <UserPoolId> --username <email>
   aws cognito-idp admin-add-user-to-group --user-pool-id <UserPoolId> --username <email> --group-name authority
   ```
   Citizens use the group `citizen`. API Gateway checks the token on the authority routes and the Lambda checks the group.
5. Email copies of alerts (optional): `EnableEmail=true AlertsEmail=<address>`, then confirm the SNS subscription email.

AWS services used: Lambda, API Gateway (HTTP API), DynamoDB. Prepared and off by default: Cognito, SNS.
`template.yaml` was checked for YAML syntax and references only; `sam validate` was not available here.

## Put the website on Vercel (demo mode, free)

The website in `frontend/` is plain files with no build step, so Vercel can host it as is. Opened without `?api=`, it runs in **demo mode** on the saved samples and needs no server and no keys. The badge says "Saved sample". Live data needs the backend (AWS Lambda, see "Deploy to AWS"), which Vercel does not run.

1. Go to https://vercel.com/new and sign in with GitHub.
2. Import the `Parali_Mitra` repository.
3. Set **Root Directory** to `smoke-path/frontend`.
4. Set **Framework Preset** to `Other`. Leave Build Command and Output Directory empty.
5. Click **Deploy**. Do not add any environment variables; the website needs none.
6. Open the `.vercel.app` link. To use it as the production site, make sure `main` is the Production Branch under Settings, Git.

To show live data later, deploy the backend to AWS, then open `https://<your-site>.vercel.app/?api=<ApiBaseUrl>`. Never put the FIRMS, OpenAQ or data.gov.in keys on Vercel or in the website; they belong only in the AWS Lambda environment.

### Making the Vercel site live (after the AWS backend exists)

Put the `ApiBaseUrl` from the stack outputs into `frontend/index.html` (`window.PM_CONFIG = { api: "<ApiBaseUrl>" ... }`),
commit and push; Vercel redeploys. The site then shows live data by default. `?demo=1` forces the saved sample, and `?api=<url>`
still overrides the default. The address is public, so it is not a secret; the keys stay in the Lambda.
