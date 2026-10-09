# Smoke Path Map (Parali Mitra, Feature 6)

Farmers who burn do not report it, so the main screen starts from what NASA satellites see.

**Fire watch (first tab).** Every fire NASA satellites saw in and around Punjab and Haryana in the
last day, where each fire's smoke is likely going, and which villages, towns, schools and hospitals
it will reach, and roughly when:

* the region summary: how many fires, **what was burning** (farm, industrial / brick kiln, built-up
  area, forest, grassland), how many villages, schools and hospitals get smoke, and the most affected
  places ("Shared Village: smoke from 2 fires, from about 3:30 pm");
* **air quality where the smoke goes**: India's AQI (CPCB) with PM2.5, PM10, CO, NO2, SO2 and ozone
  at every place on a smoke path, how much of the PM2.5 comes from the fires, a "worst air" list,
  an AQI map layer (now, +6, +12, +24, +48 hours) and live monitoring stations;
* **"Is smoke coming to my village or school?"**: type a place, or tap any spot on the map. It also
  shows the AQI there and a 48 hour AQI outlook;
* tap a fire for every satellite detail, what was on the ground there, and "Show this fire's smoke in detail".

**What if I burn? (second tab).** A farmer picks his field and a time he might burn the paddy
straw. The app shows where the smoke would **likely** travel over the next 24 or 48 hours,
using real wind forecasts:

1. a dashed **path** from the field that follows the forecast wind,
2. a soft **band** around the path that gets wider with time (uncertainty),
3. the **villages, towns, schools and hospitals** the smoke would pass, and roughly when,
   for example: *"If you burn on 10 Oct at 2:00 pm, smoke will likely reach: Badrukhan (village) by about 4:15 pm"*,
4. today's **farm fires** nearby, seen by NASA satellites. Tap a fire to see all its details
   (time seen, satellite, confidence, fire strength, brightness, pixel size, day/night) and press
   **"Show where this fire's smoke goes"** to run the same smoke path from that fire, starting at
   the time the satellite saw it.

The farmer also enters the **field size (acres)**: the app estimates how much straw burns and how
much PM2.5 it releases, and shows the AQI expected at each place on the path.

The path is always labelled **"Likely smoke direction"**: it follows the wind. The air-quality numbers
come from the CAMS forecast plus a simple Gaussian plume per fire (see "Air quality" below); they are
estimates, not measurements.

Built with **AWS Lambda (Python 3.12) + Amazon API Gateway HTTP API**, deployed with **AWS SAM**
(an AWS open-source tool), region **ap-south-1 (Mumbai)**. The backend uses only the Python
standard library. The frontend is one HTML file with Leaflet and OpenStreetMap tiles.

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
    snapshot.py     the saved copy of OpenStreetMap places around Punjab and Haryana
    data/places_snapshot.json.gz   that saved copy (made by build_places_snapshot.py)
    fires.py        NASA FIRMS fetch + CSV parsing
    landuse.py      what was burning: land cover, mapped industry, all-year heat sources
    airquality.py   CAMS forecast (Open-Meteo) on a grid, CPCB AQI, weather for spreading smoke
    plume.py        smoke one fire adds at a place (FRP -> emissions -> Gaussian plume)
    stations.py     OpenAQ monitoring stations: latest readings and the CAMS correction
    air.py          puts CAMS, weather, stations and plumes together for places and spots
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
  frontend/map.html  the map page
  template.yaml      AWS SAM template
```

---

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

1. NASA FIRMS detections from the three VIIRS satellites in the box lat 27.6-32.6, lon 73.8-77.6
   (Punjab, Haryana and the edges of Rajasthan, Himachal, Delhi, Uttar Pradesh and Pakistan Punjab).
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

### Air quality (PM2.5 and AQI)

The AQI at a place = **the CAMS forecast** (corrected by **monitoring stations** when available)
**+ the smoke each tracked fire adds** (a plume model), turned into India's AQI.

1. **CAMS** (Copernicus Atmosphere Monitoring Service, run by ECMWF) is the global air-quality forecast
   model: PM2.5, PM10, CO, NO2, SO2, ozone and dust, 0.4° (~45 km), hourly, 5 days. Open-Meteo serves it
   free with no key. Fire watch fetches it on a fixed 22 × 25 grid (lat 26-34.4, lon 70.4-80) in
   6 parallel requests while NASA's data loads, and keeps it for an hour (CAMS updates twice a day).
2. **Stations** (optional, needs a free OpenAQ key): the latest PM2.5/PM10 of CPCB and other reference
   monitors. Where a station measures twice what CAMS says for that hour, nearby CAMS values are doubled
   (factor kept within 0.2-5, fading to none at 75 km), and the factor is kept for the forecast hours.
   Station dots on the map show the measured values. Readings are compared with CAMS at the hour they
   were measured, so older readings still work: OpenAQ's copy of India's CPCB network was about
   48 hours late when tested (9 Oct 2026), so readings up to 72 hours old are used and the map shows
   their age. On that day the stations measured a median 0.7× CAMS's PM2.5 and PM10 (0.1-7.5×), mostly
   lower where CAMS forecast desert dust.
3. **Plume per fire.** CAMS cells are too coarse to see one village downwind of one field, so each fire
   adds its own smoke along its traced path:
   * burning rate = FRP (MW) × 0.368 kg/MJ (Wooster et al. 2005), for 1 hour (assumed burn time);
   * grams per kg burned (GFED4.1 table, mostly Akagi et al. 2011): crop residue PM2.5 6.26, CO 102,
     NOx 3.11 (as NO, counted fully as NO2), SO2 0.40; grassland and forest have their own values;
     industrial fires are not modelled (biomass factors do not apply to kilns or factories);
   * a Gaussian plume: sideways spread from the Briggs open-country curves for the Pasquill stability
     class (from 10 m wind, sunshine and cloud) plus the path's own uncertainty (half the band radius);
     upward spread capped by the **mixing height** (boundary layer). Low night-time mixing heights trap
     smoke near the ground, which is why winter nights are worst.
   * "What if I burn?" uses the field size instead of FRP: acres × 6.3 t straw/ha (Punjab: ~20 Mt from
     ~3.2 Mha of paddy) × 0.8 burned.
   * Mixing height, 10 m wind, sunshine and cloud come from the Open-Meteo forecast on a 0.8° grid.
4. **AQI** (CPCB National AQI): a sub-index per pollutant from CPCB's breakpoints, using 24 hour means
   for PM2.5, PM10, NO2 and SO2 and the highest 8 hour mean of the last 24 hours for CO and ozone. The AQI
   is the highest sub-index (at least 3 pollutants including PM2.5 or PM10). The page shows CPCB's
   category, colour and health advice, the main pollutant, and a cigarette equivalent
   (22 µg/m³ PM2.5 for a day ≈ 1 cigarette, Berkeley Earth).

When CAMS's PM10 is mostly desert dust, the page and summary say so ("mostly PM10, largely desert
dust"), so dust episodes are not blamed on the fires.

**Why no machine-learning model.** We looked for ready-made air-quality models with published weights
that cover India. AFNO-PM2.5 (IIT Delhi AISEHack) only takes 2016 WRF-Chem simulation fields, so it cannot
run on live data. The FLAME Weather4Cast 2025 India model has no released weights. Microsoft Aurora's
air-pollution model (Nature 2025) is the strongest, but it needs global CAMS analysis fields from the
Copernicus ADS (13 pressure levels, ~400 MB a run) and a large GPU, cannot run on AWS Lambda, and its
output is the same ~45 km grid as CAMS, which Aurora was trained to emulate. Using CAMS directly, plus a
plume model for village-scale smoke and station correction, is live, cheap and explainable.

---

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
account settings. Without it everything works, with no station correction and no station dots.

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
`python3.12 scripts/save_fixtures.py --air-only` refreshes only the air-quality data of the
"What if I burn?" sample.

## Run locally (no Docker)

```bash
python3.12 scripts/local_server.py
```

* http://127.0.0.1:8000/ is the live map (fire watch first; calls the real APIs through the local server).
* http://127.0.0.1:8000/map.html is the saved sample, with no API calls.
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
| Parameter OpenAqApiKey | paste your OpenAQ key (hidden; leave empty for no station correction) |
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
`fire_type_confidence`, `fire_type_reason`, `land_cover` (% by class), `smoke_rate` (g/s, null when
not modelled)), `fire_path` (hourly line with `times` and `km`), `reached`
(`name`, `name_local`, `place_type`, `near_town` (nearest town within 25 km, to tell apart villages with
the same name), `fires`, `first_arrival`, `arrivals` = up to 5 `[fire id, time]`, and `air`),
`aq_grid` (AQI on the CAMS grid: `south`, `west`, `step`, `rows`, `cols`, `times`, `aqi[time][node]`)
and `station` (`name`, `provider`, `time`, `pm2_5`, `pm10`).
`air` = `{t, aqi, category, dominant, pm2_5, pm2_5_fires, pm2_5_24h, pm10, co (mg/m³), no2, so2, o3, dust,
cigarettes}` (µg/m³ unless noted) at the hour the fires' smoke is strongest there.
Top level: `summary`, `stats` (incl. `fire_types`), `air` (what the numbers are based on: `stations`,
`corrected`, `fire_plumes`, forecast range), `notes`, `generated_at`, `region`.
Errors: 503 without a FIRMS key, 502 if NASA FIRMS or the wind forecast fails.
Replies over 50 KB are gzipped when the client sends `Accept-Encoding: gzip` (browsers always do);
a busy day's fire watch is 1-2 MB raw and about 0.2 MB gzipped.

### `GET /air?lat=30.9&lon=75.85` (one spot)

The 48 hour AQI outlook at a spot (CAMS, station-corrected, plus the smoke of the fires in the latest
fire watch, which it builds if needed). JSON: `now`, `worst`, `outlook` (hourly `air` dicts with `t`),
`fires` (which fires add smoke here and how much), `air`, `notes`. Cached 30 minutes per ~1 km.

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

* The path only **follows the wind**. The smoke amounts come from a simple Gaussian plume on top of
  that path; it does not model plume rise above the mixing layer, chemistry (NO is counted as NO2),
  rain washout or terrain. It is not a dispersion model like HYSPLIT.
* Fire smoke amounts rest on assumptions: each detected fire burns for 1 hour at the power the
  satellite measured (fires between satellite passes are missed or under-counted), and a field has
  6.3 t of straw per hectare, 80% of which burns.
* CAMS already includes fire emissions at ~45 km, so adding our plumes can count a little of the same
  smoke twice; CAMS is known to under-predict stubble smoke in Punjab, so we accept that.
* CAMS sometimes forecasts strong desert dust over Punjab, Haryana and Rajasthan, giving very high PM10
  and "Severe" AQI. The page labels this as dust. Station correction (OpenAQ key) pulls it towards
  measured values near stations; far from stations the CAMS value is used as it is.
* The AQI shown is CPCB's method on forecast hourly values; the official AQI comes from measured
  averages at monitoring stations.
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
