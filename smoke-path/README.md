# Smoke Path Map (Parali Mitra, Feature 6)

A farmer picks his field on a map and a time he might burn the paddy straw.
The app shows where the smoke would **likely** travel over the next 24 or 48 hours,
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
    app.py          Lambda handler, request checks, 30-minute cache, sample=true
    pipeline.py     runs one request: 2 wind calls, band, places + fires in parallel
    wind.py         Open-Meteo forecast + ensemble, wind vectors, time interpolation
    trajectory.py   15-minute RK2 path tracing, refine sites, cone band (puffs)
    ensemble.py     optional ensemble band (ICON-EPS members)
    places.py       Overpass query, closest point on the path, arrival times
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
5. **Places.** OpenStreetMap (Overpass) finds towns within 15 km, villages within 5 km and schools,
   colleges, hospitals and clinics within 3 km of the path. For each place we find the closest point
   on the path, the time the smoke is there, and whether it is inside the band at that time.
6. **Fires.** NASA FIRMS VIIRS detections (S-NPP, NOAA-20, NOAA-21) in about 1° around the field, last day.
   Each fire has the minute the satellite saw it (`acq_date` + `acq_time`, UTC). Tracing a fire
   (`origin=fire`) runs steps 1-5 from the fire's position starting at that time; because that time is
   in the past, the wind request adds Open-Meteo's `past_days` (up to 3 days back).

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

## Run locally (no Docker)

```bash
python3.12 scripts/local_server.py
```

* http://127.0.0.1:8000/ is the live map (calls the real APIs through the local server).
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
* Places come from the public Overpass server, which is sometimes overloaded (it was on 9 Oct 2026).
  Then the reply still comes back, with the note "Places unavailable", and the summary says places could
  not be checked. Set `OverpassUrl` to another Overpass server if the main one stays down.
* Places come from OpenStreetMap, which is incomplete in rural areas; a missing school is not a safe school.
* Fires are satellite detections from the last day. Clouds hide fires, and small fires can be missed.
* A fire's time is when the satellite passed over (VIIRS passes Punjab around 1:30 am and 1:30 pm), not
  when the fire was lit. Tracing from that time shows where its smoke went from then on.

## Data sources and terms

* Wind: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0, free for non-commercial use).
* Places: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL), via the
  [Overpass API](https://overpass-api.de/). Please keep request volumes low.
* Fires: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) VIIRS active fire data (free MAP_KEY).
* Map tiles: OpenStreetMap (attribution shown on the map).
