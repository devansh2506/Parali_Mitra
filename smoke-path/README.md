# Smoke Path Map (Parali Mitra, Feature 6)

Farmers who burn do not report it, so the main screen starts from what NASA satellites see.

**Fire watch (first tab).** Every fire NASA satellites saw in and around Punjab and Haryana in the
last day, where each fire's smoke is likely going, and which villages, towns, schools and hospitals
it will reach, and roughly when:

* the region summary: how many fires, how many villages, schools and hospitals get smoke, and the
  most affected places ("Shared Village: smoke from 2 fires, from about 3:30 pm");
* **"Is smoke coming to my village or school?"**: type a place, or tap any spot on the map;
* tap a fire for every satellite detail and "Show this fire's smoke in detail".

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

It is always labelled **"Likely smoke direction"**. It is a simple wind model, not a smoke dispersion model.

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

---

## Run the tests (no network needed)

```bash
cd smoke-path
python3.12 -m unittest discover -s tests -v
```

---

## Your FIRMS key (for fires)

Put it in `smoke-path/.env` (copy `.env.example`); the scripts read it automatically and git ignores it:

```
FIRMS_MAP_KEY=<YOUR_FIRMS_MAP_KEY>
```

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
`details` with every detection), `fire_path` (hourly line with `times` and `km`) and `reached`
(`name`, `name_local`, `place_type`, `near_town` (nearest town within 25 km, to tell apart villages with
the same name), `fires`, `first_arrival`, `arrivals` = up to 5 `[fire id, time]`).
Top level: `summary`, `stats`, `notes`, `generated_at`, `region`.
Errors: 503 without a FIRMS key, 502 if NASA FIRMS or the wind forecast fails.
Replies over 50 KB are gzipped when the client sends `Accept-Encoding: gzip` (browsers always do);
a busy day's fire watch is 1-2 MB raw and about 0.2 MB gzipped.

### `GET /smoke` (one smoke path)

`GET /smoke?lat=30.245&lon=75.844&start=2026-10-10T14:00&hours=24&uncertainty=cone`

| Parameter | Meaning |
| --- | --- |
| `lat`, `lon` | required, decimal degrees |
| `start` | optional, India time `YYYY-MM-DDTHH:MM`; default the next full hour |
| `hours` | optional, 1 to 48, default 24 |
| `uncertainty` | optional, `cone` (default) or `ensemble` |
| `origin` | optional, `field` (default: a planned burn, `start` today or later) or `fire` (a fire already seen by satellite: `start` = the time it was seen, required, up to 3 days back) |
| `sample=true` | returns the saved demo response, with `"sample": true`, no external calls |

The reply is a GeoJSON FeatureCollection. Every feature has `properties.kind`:
`field`, `path` (with `km`), `puff` (one per hour: `hour`, `time`, `radius_km`),
`member` (ensemble only), `place` (`name`, `name_local`, `place_type`, `distance_km`, `arrival`,
`arrival_text`, `in_band`) and `fire` (`date`, `time_utc`, `time_ist`, `date_ist`, `seen_at`, `seen_text`,
`confidence`, `frp`, `bright_ti4`, `bright_ti5`, `scan`, `track`, `satellite`, `instrument`, `daynight`,
`version`, `source`).
Top level: `label`, `summary` (headline, then one line per place), `notes` (warnings), `wind_level`,
`uncertainty`, `origin`, `sample`.

Errors: **400** `{"error": "..."}` for bad input or a time outside the forecast; **502** only when the
wind forecast itself fails. If places or fires fail, the reply is still **200** with a note.

Settings (Lambda environment variables): `FIRMS_MAP_KEY` (from the `FirmsMapKey` parameter),
`WIND_LEVEL` (`10m`, `80m`, `120m` or `180m`, default `120m`) and `OVERPASS_URL` (default
`https://overpass-api.de/api/interpreter`).

---

## Limits of the model (please read)

* It only **follows the wind**. It does not model how smoke rises, spreads, settles or reacts
  chemically, and it does not say how much smoke arrives. It is not a dispersion model like HYSPLIT.
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
* Fires: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) VIIRS active fire data (free MAP_KEY).
* Map tiles: OpenStreetMap (attribution shown on the map).
