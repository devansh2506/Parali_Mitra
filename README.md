# Parali Mitra (पराली मित्र)

**Satellites see the fires. Parali Mitra shows what is burning, how toxic it is, where the smoke will go, and warns the people in its way.**

It is a web app for crop-residue ("parali") burning in India, built for the WeMakeDevs x AWS hackathon (8 to 11 October 2026). It runs entirely on AWS: S3 and CloudFront serve the app, API Gateway and Lambda do the work, DynamoDB keeps alerts and cases, and EventBridge refreshes the data every 30 minutes.

Demo (may be taken down after the hackathon): https://d1qht8bqoe1eyl.cloudfront.net

---

## Who it is for: three logins

The landing page has three logins. They share one design, one backend and one set of data. The login is a demo login with no password (Amazon Cognito sign-in is prepared but off).

| Role | What they do |
|---|---|
| **Farmer** | Registers a farm. Sees fires and smoke near it, and warnings from authorities (with an "I have read this" button). Keeps a crop list with a care guide, uses a symptom-based crop doctor, and works out what burning straw would release. Takes a no-burn pledge and prints a certificate. English and Hindi. |
| **Citizen** | Picks an area. Sees the air now and for the next 48 hours, whether smoke is coming, health advice, a calm map of fires and air stations, and alerts from authorities. English and Hindi. |
| **Authority** | A control room: every fire in India with its type and toxicity, a map with animated smoke paths, filters by fire type and state. Warns the person behind a fire (farmer, factory or kiln owner, municipal body) with editable English and Hindi messages, alerts the people on the smoke path, and tracks each fire as a case (new, warning sent, acknowledged, resolved, dismissed) with a timeline and an activity log. |

The roles are connected. An authority's warning to a farmer reaches that farmer's Warnings page. When the farmer taps "I have read this", the fire's case becomes *acknowledged* on the authority side.

A badge in the top bar always says where the data came from: green **Live**, blue **Part live, part saved**, or amber **Saved sample**. A small clock shows the real time in India next to it.

---

## How the data flows (plain English)

**1. Fires.** NASA's VIIRS satellites look for heat from space and NASA publishes every hot spot (service: FIRMS). We ask for the last 2 days and keep the last 24 hours, inside India's border. Each hot spot has a place, a time, how strong the heat is (fire radiative power) and how sure the satellite is. Data is about 3 hours behind each satellite pass.

**2. What was burning.** A satellite only sees heat, so the cause is a guess from the ground under the fire, checked in this order: a known permanent heat source or mapped industry (only around Delhi, Punjab and Haryana, where we have that data), then the land cover from ESA WorldCover (farmland, forest, grassland, built-up). Every label has a reason. Factory and kiln fires elsewhere can show up as farm, built-up or unknown, and the app says so.

**3. How toxic.** Plain arithmetic, no machine learning. Heat strength gives the amount of plant material burning (0.368 kg per megajoule). Published emission tables give what each kilo releases (GFED4.1: PM2.5, CO, NO2, SO2, black carbon and more). Then we ask how much clean air that smoke spoils beyond India's safe limits, in km³ of air per hour, grouped into low, moderate, high and very high. It compares fires with each other; it does not predict the air at your door. Industrial and landfill fires are not estimated.

**4. Wind and the smoke path.** Wind speed and direction at 120 m come from Open-Meteo on a grid over India (about 530 points, refreshed every 6 hours), for the last 3 days and the days ahead. From a fire we move a "leaf" hour by hour with the wind: backwards with past wind to see where the smoke already went, forwards with the forecast to see where it is heading. Places within a few kilometres of that line get a time: "smoke reaches Bisoi about 9 pm". Cities and towns are listed for all of India; villages, schools and hospitals only for the north-west. This is a wind-carry line: it gives direction and timing, not how thick the smoke is.

**5. Air quality.** The AQI is calculated in code with the Indian national method (CPCB breakpoints; the worst pollutant sets the AQI). *Forecast*: the CAMS atmosphere model through Open-Meteo, 48 hours, drawn as a smooth gradient. *Measured*: OpenAQ monitoring stations with PM2.5, PM10, NO2, SO2, CO and ozone where available. OpenAQ's copy of the government readings is often 2 to 4 days old, so the AQI is marked indicative and every reading shows its age. Fires and air quality are two separate views; no fire smoke is added on top of the forecast.

**6. Alerts and cases.** Warnings and alerts are saved in DynamoDB (in the browser in demo mode). Citizens see alerts within about 15 km of their area; farmers see warnings about fires within 25 km of their farm (contact details are never shown to them).

| Data | Freshness | Refreshed |
|---|---|---|
| Fires | about 3 hours behind the satellite | every 30 minutes (and by visitors if older) |
| Wind grid | recent past and the days ahead | every 6 hours |
| Air forecast | next 48 hours | every 6 hours |
| Measured air | 2 to 4 days old (OpenAQ) | every 30 minutes |
| Towns, land cover, states | shipped with the app | only when rebuilt |

---

## How it is built

```
Browser ──> CloudFront ──┬──> S3 (the web app, private bucket)
                         └──> API Gateway ──> Lambda (Python 3.12, standard library only)
                                                   ├──> DynamoDB   alerts and cases
                                                   └──> S3         shared cache of the slow results
EventBridge (every 30 min) ──> Lambda "warm" ──> refreshes fires, stations and forecast
```

* **AWS services:** S3, CloudFront, API Gateway (HTTP API), Lambda, DynamoDB, EventBridge. Optional and off by default: Cognito sign-in and SNS email (`template.yaml`).
* **Why the shared cache:** fetching fires, the wind grid and the air forecast takes about 25 seconds, and API Gateway cuts a request at 29 seconds. The scheduled refresh keeps a copy in S3, so a visitor normally gets an answer in about 2 seconds, and Open-Meteo's free daily limit is not spent again by every Lambda restart.
* **Frontend:** plain JavaScript, no build step, Leaflet for maps, English and Hindi text in one file. With no `?api=` the page runs in *demo mode* on saved samples (works offline); on AWS the page and the API share one address, so it is live.
* **Backend:** standard library only (plus boto3, which Lambda provides). No machine learning model: the numbers come from published formulas and tables.

### Folder layout

```
smoke-path/            the app
  src/smoke_path/      backend (fires, wind, smoke path, emissions, air, alerts, shared cache, Lambda handler)
  frontend/            the web app (js/, css/, data/ with saved samples and reference lists)
  scripts/             local server, AWS deploy script, one-time data builders
  fixtures/            saved real responses used for samples and tests
  tests/               unit tests (no network needed)
  template.yaml        the AWS stack (SAM / CloudFormation)
  DEMO_SCRIPT.md       a 3-minute demo walk-through
kissan-sarthi/         a separate Next.js farming assistant this project drew ideas from (not deployed by the AWS stack)
```

---

## Run it on your computer

You need Python 3.12 and two free keys in `smoke-path/.env` (this file is gitignored; never commit it):

```
FIRMS_MAP_KEY=<your NASA FIRMS key>         # https://firms.modaps.eosdis.nasa.gov/api/map_key/
OPENAQ_API_KEY=<your OpenAQ key>            # https://explore.openaq.org/register
```

```
cd smoke-path
python3.12 scripts/local_server.py --port 8765
```

Open http://127.0.0.1:8765/ for live data (the first load takes about 25 seconds), or http://127.0.0.1:8765/index.html for the saved sample. Press Ctrl+C to stop.

Tests (no network, about 3 seconds):

```
cd smoke-path
python3.12 -m unittest discover -s tests
```

---

## Deploy to AWS

One time: `brew install awscli aws-sam-cli`, then `aws configure` (an IAM user's access key and your region), and put the two keys in `smoke-path/.env`.

```
cd smoke-path
bash scripts/deploy_aws.sh
```

The script builds, deploys the stack `parali-mitra`, uploads the web app, clears the CloudFront cache, starts the first data fetch and prints the address of your site. The first run takes about 10 minutes (CloudFront is slow to create); later runs take 2 to 3 minutes and keep the same address. Run it again after any change. The keys go to AWS as hidden stack parameters and are never printed or stored in git.

Take it down: empty the two S3 buckets (site and cache), then delete the stack `parali-mitra` in CloudFormation, then delete the IAM user.

Cost: for a demo, expected well under 5 dollars a month (Lambda, API Gateway, DynamoDB and S3 are tiny at this scale and CloudFront's first terabyte is free). Set a budget alarm anyway.

---

## API

All answers are JSON. Slow ones are served from the shared cache.

| Endpoint | What it gives |
|---|---|
| `GET /fires?hours=24` | Every fire in India: type and reason, emissions, toxicity, smoke path, places reached |
| `GET /stations` | Latest readings and AQI at monitoring stations, city table, rankings |
| `GET /forecast` | AQI on the region grid every 3 hours for 48 hours (the map layer) |
| `GET /air?lat=&lon=` | 48-hour AQI outlook at one spot |
| `GET /smoke?lat=&lon=&start=&hours=` | One smoke path from a chosen point and time |
| `POST /alerts` | Authority: warn a fire's source, or alert people on its smoke path |
| `GET /alerts?lat=&lon=&radius_km=` | Public alerts that affect an area (the citizen inbox) |
| `GET /alerts?...&kind=farmer_warnings` | Warnings sent to farmers about fires near a farm |
| `POST /alerts/{id}/ack` | Farmer confirms a warning was read (case becomes acknowledged) |
| `GET /activity`, `GET /cases`, `PATCH /cases/{id}` | Authority: alerts sent, cases and their status |

With sign-in switched off (the default), the authority routes are open to anyone with the address. That is fine for a private demo; turn on Cognito (`EnableAuth=true` in `template.yaml`) before any public use.

---

## Data sources and terms

| Source | Used for | Key |
|---|---|---|
| NASA FIRMS (VIIRS) | Fire hot spots | free key |
| Open-Meteo | Wind grid and the CAMS air forecast (free tier: 10,000 point-calls a day, non-commercial use) | none |
| CAMS global atmospheric composition forecast (ECMWF) | 48-hour air forecast | none, through Open-Meteo |
| OpenAQ | Measured air at stations | free key |
| ESA WorldCover 2021 | What was on the ground (land cover) | shipped with the app |
| OpenStreetMap | Industry, towns and places (shipped snapshot); fallback map tiles | none |
| Esri | Base map tiles | none |
| GFED4.1 emission factors, Wooster et al. 2005 | Emission and toxicity arithmetic | published tables |
| CPCB National Air Quality Index | AQI method and colours | published standard |

---

## Honest limits

* The smoke path shows direction and timing, not smoke thickness.
* Fire type is a guess from land cover. Factory and kiln fires can only be recognised near Delhi, Punjab and Haryana; elsewhere they may look like farm, built-up or unknown.
* Toxicity is a comparison between fires, not a forecast of the air at a place. It is not estimated for industrial and landfill fires.
* Measured air from OpenAQ is often 2 to 4 days old. The forecast is a coarse model and can show very high values in dust events.
* Villages, schools and hospitals are listed only for the north-west.
* The crop doctor matches the symptoms a farmer ticks to common diseases. It does not analyse a photo; it is guidance, not a diagnosis. Costs and subsidies for straw alternatives are indicative: confirm with the local Krishi Vigyan Kendra.
* The farm, crops and pledges stay in the farmer's browser. Demo contacts are obviously fake. The no-burn certificate is a demo, not a government document.
* A warning is matched to a farm by distance, not to one named farmer: there is no land-records link.
* The saved sample in `frontend/data` is from 10 October 2026, 3 pm. It had no fires in Punjab, so the demo story uses real fires in Jharkhand and Odisha.

---

## Kissan Sarthi

`kissan-sarthi/` is a separate Next.js and FastAPI farming assistant (farm registration, crop care, a crop doctor, stubble pledges). Its ideas, such as the stubble alternatives and the no-burn pledge, were brought into the Farmer role here, with the pollution numbers switched to this project's own model so the two agree. It is not part of the AWS deployment.
