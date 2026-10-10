"""Fire type, CPCB AQI, the CAMS grid, the smoke plume, stations and GET /air. No network."""

import json
import math
import unittest
from datetime import datetime, timedelta

from helpers import DAY0, FakeApi, GRID_T0, const_grid, const_series

from smoke_path import IST, air, airquality, app, emissions, firewatch, landuse, stations
from smoke_path.airquality import FieldGrid, aqi, averages, category, parse_hourly_points, sub_index
from smoke_path.app import ResponseCache, handle


class FireTypeTests(unittest.TestCase):
    """landuse.classify with tiny made-up data (not the shipped files)."""

    def lc(self, rows):
        """A 9x9 land cover grid at 0.001 degrees around (30.0, 75.0) from row strings of class codes."""
        header = {"south": 29.9955, "west": 74.9955, "north": 30.0045, "east": 75.0045, "step": 0.001, "rows": 9, "cols": 9}
        return landuse.Landcover(header, bytes(int(ch) for row in rows for ch in row))

    def setUp(self):
        self.crop = self.lc(["4" * 9] * 9)
        self.town = self.lc(["5" * 9] * 9)
        self.none = landuse.Industry([])
        self.no_static = landuse.StaticSources([])

    def classify(self, lc, ind=None, sta=None, lat=30.0, lon=75.0):
        return landuse.classify(lat, lon, lc=lc, ind=ind or self.none, sta=sta or self.no_static)

    def test_coarse_national_grid_answers_only_where_the_fine_one_does_not(self):
        fine = self.lc(["5" * 9] * 9)  # built-up around (30, 75)
        wide = landuse.Landcover({"south": 26.98, "west": 71.98, "north": 27.02, "east": 72.02, "step": 0.004, "rows": 10, "cols": 10},
                                 bytes([4]) * 100)  # cropland everywhere, 0.004 degree (~450 m) cells around (27, 72)
        wide_all = landuse.Landcover({"south": 29.98, "west": 74.98, "north": 30.02, "east": 75.02, "step": 0.004, "rows": 10, "cols": 10},
                                     bytes([4]) * 100)
        stack = landuse.LandcoverStack([fine, wide, wide_all])
        self.assertEqual(self.classify(stack)["category"], "settlement")  # the detailed grid wins
        far = self.classify(stack, lat=27.0, lon=72.0)  # only the national grid knows this spot
        self.assertEqual((far["category"], far["confidence"]), ("farm", "medium"))  # never 'high' from the coarse map
        self.assertIn("coarse", far["reason"])

    def test_cropland_is_a_farm_fire(self):
        r = self.classify(self.crop)
        self.assertEqual((r["category"], r["kind"], r["confidence"]), ("farm", "crop residue", "high"))
        self.assertEqual(r["cover"], {"cropland": 100})
        self.assertIn("100% cropland", r["reason"])

    def test_built_up_and_mixed(self):
        self.assertEqual(self.classify(self.town)["category"], "settlement")
        mixed = self.lc(["4" * 9] * 3 + ["1" * 9] * 3 + ["3" * 9] * 3)  # crop, trees, grass: none >= 50%
        r = self.classify(mixed)
        self.assertIn(r["category"], ("farm", "forest", "grassland"))
        self.assertEqual(r["confidence"], "low")

    def test_static_heat_source_wins(self):
        sta = landuse.StaticSources([{"lat": 30.001, "lon": 75.0, "days": 9, "type2": False, "period": "Jul 2025 to Jun 2026"}])
        r = self.classify(self.crop, sta=sta)
        self.assertEqual((r["category"], r["confidence"]), ("industrial", "high"))
        self.assertIn("9 days outside the crop-burning seasons", r["reason"])
        far = landuse.StaticSources([{"lat": 30.01, "lon": 75.0, "days": 9, "type2": True, "period": "x"}])  # 1.1 km
        self.assertEqual(self.classify(self.crop, sta=far)["category"], "farm")

    def test_mapped_kiln_and_landfill(self):
        kiln = landuse.Industry([{"kind": "kiln", "name": "Shiv Bricks", "lat": 30.002, "lon": 75.0, "r_km": 0.0}])
        r = self.classify(self.town, ind=kiln)  # 220 m from a kiln, not a field
        self.assertEqual((r["category"], r["kind"]), ("industrial", "brick kiln"))
        self.assertIn("Shiv Bricks", r["reason"])
        # In open farmland a kiln nearby only lowers the confidence: the field may be what burned.
        r = self.classify(self.crop, ind=kiln)
        self.assertEqual((r["category"], r["confidence"]), ("farm", "low"))
        dump = landuse.Industry([{"kind": "landfill", "name": "", "lat": 30.0, "lon": 75.0, "r_km": 0.3}])
        self.assertEqual(self.classify(self.crop, ind=dump)["category"], "waste")

    def test_inside_an_industrial_area(self):
        area = landuse.Industry([{"kind": "industrial", "name": "Focal Point", "lat": 30.0, "lon": 75.003, "r_km": 0.5}])
        r = self.classify(self.crop, ind=area)
        self.assertEqual((r["category"], r["confidence"]), ("industrial", "high"))
        self.assertTrue(r["reason"].startswith("inside a mapped industrial area"))

    def test_outside_the_land_cover(self):
        r = self.classify(self.crop, lat=31.0)
        self.assertEqual(r["category"], "unknown")

    def test_cluster_any_industrial_detection_wins(self):
        sta = landuse.StaticSources([{"lat": 30.003, "lon": 75.0, "days": 5, "type2": True, "period": "x"}])
        data = {"lc": self.crop, "ind": self.none, "sta": sta}
        r = landuse.classify_cluster([(29.9965, 75.0), (29.9965, 75.0), (30.003, 75.0)], **data)
        self.assertEqual(r["category"], "industrial")

    def test_shipped_files_load(self):
        self.assertIsNotNone(landuse.landcover())
        self.assertGreater(len(landuse.industry().rows), 100)
        self.assertGreater(len(landuse.static_sources().cells), 10)
        self.assertEqual(landuse.classify(30.73, 76.78)["category"], "settlement")  # Chandigarh


class AqiTests(unittest.TestCase):
    def test_sub_index_breakpoints(self):
        self.assertEqual(sub_index("pm2_5", 30), 50)
        self.assertEqual(sub_index("pm2_5", 60), 100)
        self.assertEqual(sub_index("pm2_5", 90), 200)
        self.assertEqual(sub_index("pm2_5", 105), 250)
        self.assertEqual(sub_index("pm2_5", 250), 400)
        self.assertEqual(sub_index("pm2_5", 2000), 500)  # capped
        self.assertEqual(sub_index("pm10", 100), 100)
        self.assertEqual(sub_index("co", 2000), 100)  # µg/m³ in, mg/m³ breakpoints
        self.assertEqual(sub_index("o3", 168), 200)

    def test_categories(self):
        self.assertEqual([category(x)[0] for x in (0, 50, 51, 100, 200, 300, 400, 401, 500)],
                         ["good", "good", "satisfactory", "satisfactory", "moderate", "poor", "very_poor", "severe", "severe"])

    def test_aqi_needs_three_pollutants_with_pm(self):
        self.assertIsNone(aqi({"pm2_5": 50, "no2": 10}))
        self.assertIsNone(aqi({"no2": 10, "so2": 10, "o3": 10}))
        r = aqi({"pm2_5": 95, "pm10": 120, "no2": 30})
        self.assertEqual((r["aqi"], r["dominant"], r["category"]), (217, "pm2_5", "poor"))

    def test_averaging_windows(self):
        hours = 30
        series = {"pm2_5": [0.0] * 6 + [48.0] * 24, "co": [0.0] * 22 + [4000.0] * 8, "o3": [10.0] * hours}
        avg = averages(series, hours - 1)
        self.assertAlmostEqual(avg["pm2_5"], 48.0)  # last 24 hours only
        self.assertAlmostEqual(avg["co"], 4000.0)  # the highest 8 hour mean
        self.assertNotIn("pm10", avg)
        self.assertIsNone(averages({"pm2_5": [1.0] * 10}, 9).get("pm2_5"))  # < 16 hours

    def test_cigarettes(self):
        self.assertEqual(airquality.cigarettes(44), 2.0)


class GridTests(unittest.TestCase):
    def test_parse_multi_point_reply_and_fill_gaps(self):
        times = [(DAY0 + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(4)]
        item = {"utc_offset_seconds": 19800, "hourly": {"time": times, "pm2_5": [None, 2, None, 4], "ozone": [1, 1, 1, 1]}}
        t0, data = parse_hourly_points([item, item], {"pm2_5": "pm2_5", "ozone": "o3"}, "test")
        self.assertEqual(t0, DAY0)
        self.assertEqual(data["pm2_5"], [[2.0, 2.0, 2.0, 4.0]] * 2)
        bad = {"hourly": {"time": times, "pm2_5": [None] * 4, "ozone": [1] * 4}}
        with self.assertRaises(Exception):
            parse_hourly_points([bad], {"pm2_5": "pm2_5", "ozone": "o3"}, "test")

    def test_bilinear_windows_and_time(self):
        spec = {"south": 30.0, "west": 75.0, "step": 0.4, "rows": 2, "cols": 2}
        values = {"pm2_5": [[float(h) for h in range(48)], [10.0 + h for h in range(48)], [0.0] * 48, [0.0] * 48]}
        g = FieldGrid(**spec, t0=DAY0, values=values)
        self.assertAlmostEqual(g.value("pm2_5", 30.0, 75.2, 5), 10.0)  # halfway between 5 and 15
        self.assertAlmostEqual(g.mean("pm2_5", 30.0, 75.0, 0, 3), 1.5)
        self.assertAlmostEqual(g.mean("pm2_5", 30.0, 75.0, -5, 1), 0.5)  # clamped to the data
        self.assertAlmostEqual(g.at("pm2_5", DAY0 + timedelta(minutes=90), 30.0, 75.0), 1.5)

    def test_aq_url_has_all_variables(self):
        url = airquality.aq_url([(30.0, 75.4), (30.4, 75.8)], 3, 3)
        self.assertIn("latitude=30,30.4", url)
        self.assertIn("domains=cams_global", url)
        for v in airquality.VARIABLES:
            self.assertIn(v, url)






class StationTests(unittest.TestCase):
    NOW = datetime(2026, 10, 9, 18, 0, tzinfo=IST)

    def locations(self):
        fresh = "2026-10-09T12:00:00Z"  # 17:30 IST
        return {"results": [
            {"id": 1, "name": "A", "coordinates": {"latitude": 30.90, "longitude": 75.85}, "datetimeLast": {"utc": fresh},
             "provider": {"name": "CPCB"}, "sensors": [{"id": 11, "parameter": {"id": 2}}, {"id": 12, "parameter": {"id": 1}}]},
            {"id": 2, "name": "B", "coordinates": {"latitude": 30.91, "longitude": 75.86}, "datetimeLast": {"utc": "2026-10-09T11:00:00Z"},
             "provider": {"name": "CPCB"}, "sensors": [{"id": 21, "parameter": {"id": 2}}]},  # same cell, older
            {"id": 3, "name": "Old", "coordinates": {"latitude": 29.0, "longitude": 76.0}, "datetimeLast": {"utc": "2026-10-01T00:00:00Z"},
             "sensors": [{"id": 31, "parameter": {"id": 2}}]},
        ]}

    def test_active_monitors_one_per_cell(self):
        locs = stations.pick(stations.parse_locations(self.locations(), self.NOW))
        self.assertEqual([x["name"] for x in locs], ["A"])
        self.assertEqual(locs[0]["sensors"], {11: "pm2_5", 12: "pm10"})

    def test_latest_values(self):
        loc = stations.parse_locations(self.locations(), self.NOW)[0]
        data = {"results": [
            {"datetime": {"utc": "2026-10-09T12:00:00Z"}, "value": 88.5, "sensorsId": 11},
            {"datetime": {"utc": "2026-10-09T12:00:00Z"}, "value": -3, "sensorsId": 12},  # bad value
        ]}
        s = stations.parse_latest(data, loc, self.NOW)
        self.assertEqual((s["pm2_5"], s["pm10"]), (88.5, None))
        self.assertIsNone(stations.parse_latest({"results": []}, loc, self.NOW))

    def test_gases_are_read_and_the_station_with_most_pollutants_wins_its_cell(self):
        fresh = {"utc": "2026-10-09T12:00:00Z"}
        data = {"results": [
            {"id": 1, "name": "PM only", "coordinates": {"latitude": 30.90, "longitude": 75.85}, "datetimeLast": fresh,
             "sensors": [{"id": 11, "parameter": {"id": 2}}]},
            {"id": 2, "name": "Full", "coordinates": {"latitude": 30.91, "longitude": 75.86},
             "datetimeLast": {"utc": "2026-10-09T11:00:00Z"}, "provider": {"name": "CPCB"},  # older, but measures more
             "sensors": [{"id": 21, "parameter": {"id": 2}}, {"id": 22, "parameter": {"id": 5}}, {"id": 23, "parameter": {"id": 6}},
                         {"id": 24, "parameter": {"id": 102}}, {"id": 25, "parameter": {"id": 3}},
                         {"id": 26, "parameter": {"id": 5}}]},  # CO id 102 = CPCB's "ppb" CO (really mg/m³); id 5 = a dead 2018 NO2 sensor
            {"id": 3, "name": "Gas only", "coordinates": {"latitude": 25.0, "longitude": 70.0}, "datetimeLast": fresh,
             "sensors": [{"id": 31, "parameter": {"id": 5}}]},  # no particles: no AQI possible
        ]}
        locs = stations.pick(stations.parse_locations(data, self.NOW))
        self.assertEqual([x["name"] for x in locs], ["Full"])
        t = "2026-10-09T12:00:00Z"
        latest = {"results": [{"datetime": {"utc": t}, "value": v, "sensorsId": i}
                              for i, v in ((21, 90), (22, 40), (23, 12), (24, 1.5), (25, 60))]}
        latest["results"].append({"datetime": {"utc": "2018-02-21T20:45:00Z"}, "value": 77.6, "sensorsId": 26})  # too old
        s = stations.parse_latest(latest, locs[0], self.NOW)
        self.assertEqual((s["pm2_5"], s["no2"], s["so2"], s["co"], s["o3"]), (90, 40, 12, 1500, 60))  # CO kept in µg/m³
        from smoke_path import cpcb
        from unittest import mock
        with mock.patch.object(stations, "fetch_stations", return_value=[s]):
            row = cpcb.openaq_fallback("PLACEHOLDER", self.NOW)[0]
        self.assertEqual(row["pollutants"]["co"]["avg"], 1.5)  # CPCB feed shape: CO in mg/m³
        self.assertEqual(row["pollutants"]["no2"]["avg"], 40)

    def test_late_readings_up_to_five_days(self):
        loc = stations.parse_locations(self.locations(), self.NOW)[0]
        two_days = {"results": [{"datetime": {"utc": "2026-10-07T12:00:00Z"}, "value": 70, "sensorsId": 11}]}
        four_days = {"results": [{"datetime": {"utc": "2026-10-02T12:00:00Z"}, "value": 70, "sensorsId": 11}]}
        self.assertEqual(stations.parse_latest(two_days, loc, self.NOW)["pm2_5"], 70.0)  # OpenAQ's CPCB copy lags ~2 days
        self.assertIsNone(stations.parse_latest(four_days, loc, self.NOW))  # older than 5 days: not used

    def test_key_is_never_shown(self):
        from unittest import mock

        from smoke_path.net import ApiError

        with mock.patch.object(stations, "request", side_effect=ApiError("failed for https://x?k=SECRET123")):
            with self.assertRaises(ApiError) as caught:
                stations.fetch_locations_raw((30, 75, 31, 76), "SECRET123")
        self.assertNotIn("SECRET123", str(caught.exception))

    def test_toxicity_score(self):
        from smoke_path import emissions

        t = emissions.toxicity({"pm2_5": 60.0, "benzene": 5.0})  # 60 kg at 60 µg/m³ = 1 km³; 5 kg at 5 = 1 km³
        self.assertAlmostEqual(t["km3"], 2.0)
        self.assertEqual(t["shares"], {"pm2_5": 50, "benzene": 50})
        self.assertEqual(t["level"], "high")
        self.assertEqual(emissions.toxicity({"pm2_5": 1.0})["level"], "low")
        self.assertIsNone(emissions.toxicity({}))

    def test_field(self):
        from smoke_path import emissions

        f = emissions.from_field(5)
        self.assertEqual(f["per"], "field")
        self.assertAlmostEqual(f["kg"]["pm2_5"], round(emissions.burned_tonnes(5) * 6.26, 1))


class CpcbTests(unittest.TestCase):
    NOW = datetime(2026, 10, 10, 9, 30, tzinfo=IST)

    def records(self):
        rec = lambda station, city, pid, avg, lat="30.90", lon="75.85", key="avg_value": {  # noqa: E731
            "country": "India", "state": "Punjab", "city": city, "station": station, "last_update": "10-10-2026 09:00:00",
            "latitude": lat, "longitude": lon, "pollutant_id": pid, "min_value": "10", "max_value": "300", key: avg}
        return [rec("Punjab Agri Univ, Ludhiana - PPCB", "Ludhiana", "PM2.5", "95"),
                rec("Punjab Agri Univ, Ludhiana - PPCB", "Ludhiana", "PM10", "150"),
                rec("Punjab Agri Univ, Ludhiana - PPCB", "Ludhiana", "CO", "1.5"),
                rec("Punjab Agri Univ, Ludhiana - PPCB", "Ludhiana", "OZONE", "NA"),
                rec("Model Town, Ludhiana - PPCB", "Ludhiana", "PM2.5", "30", "30.89", "75.83", "pollutant_avg"),
                rec("Model Town, Ludhiana - PPCB", "Ludhiana", "NO2", "20", "30.89", "75.83", "pollutant_avg"),
                rec("Model Town, Ludhiana - PPCB", "Ludhiana", "NH3", "10", "30.89", "75.83", "pollutant_avg")]

    def test_parse_and_aqi(self):
        from smoke_path import cpcb

        found = cpcb.parse_records(self.records())
        self.assertEqual(len(found), 2)
        pau = [s for s in found if s["name"].startswith("Punjab Agri")][0]
        self.assertEqual(set(pau["pollutants"]), {"pm2_5", "pm10", "co"})  # "NA" ozone skipped
        self.assertEqual(pau["updated"], datetime(2026, 10, 10, 9, 0, tzinfo=IST))
        doc = cpcb.summarise(found, self.NOW, "test")
        by = {s["name"]: s for s in doc["stations"]}
        self.assertEqual(by["Punjab Agri Univ, Ludhiana - PPCB"]["aqi"], 217)  # PM2.5 95 -> 217
        self.assertEqual(by["Punjab Agri Univ, Ludhiana - PPCB"]["pollutants"]["co"]["sub"], 75)  # 1.5 mg/m³ is halfway from 1.0 (50) to 2.0 (100)
        self.assertEqual(by["Model Town, Ludhiana - PPCB"]["aqi"], 50)
        self.assertEqual(doc["cities"][0]["city"], "Ludhiana")
        self.assertEqual(doc["cities"][0]["aqi"], round((217 + 50) / 2))
        self.assertEqual(doc["rankings"]["focus_most_polluted"][0], "Punjab Agri Univ, Ludhiana - PPCB")
        self.assertEqual(by["Punjab Agri Univ, Ludhiana - PPCB"]["age_h"], 0.5)

    def test_city_from_openaq_name(self):
        from smoke_path import cpcb

        self.assertEqual(cpcb.city_from_name("Vikas Sadan, Gurugram - HSPCB"), "Gurugram")
        self.assertEqual(cpcb.city_from_name("New Delhi"), "New Delhi")

    def test_endpoint_caches(self):
        from smoke_path import cpcb

        calls = []

        def live(now):
            calls.append(1)
            return cpcb.summarise(cpcb.parse_records(self.records()), self.NOW, "test"), True

        cache = ResponseCache()
        r1 = app.handle_stations(cache, self.NOW, live=live)
        r2 = app.handle_stations(cache, self.NOW, live=live)
        self.assertEqual((r1["statusCode"], r2["body"] == r1["body"], len(calls)), (200, True, 1))


class ForecastEndpointTests(unittest.TestCase):
    NOW = DAY0 + timedelta(hours=14)

    def event(self, path, **q):
        return {"rawPath": path, "requestContext": {"http": {"method": "GET", "path": path}}, "queryStringParameters": q}

    def test_air_is_plain_cams(self):
        resp = handle(self.event("/air", lat="30.9", lon="75.85"), api=FakeApi(), cache=ResponseCache(), now=self.NOW)
        self.assertEqual(resp["statusCode"], 200)
        doc = json.loads(resp["body"])
        self.assertEqual(len(doc["outlook"]), 48)
        self.assertEqual(doc["now"]["pm2_5"], 60.0)  # exactly the CAMS value: nothing added
        self.assertNotIn("pm2_5_fires", doc["now"])
        self.assertEqual((doc["now"]["aqi"], doc["now"]["category"]), (100, "satisfactory"))
        self.assertTrue(doc["inside_region"])

    def test_forecast_layer(self):
        resp = handle(self.event("/forecast"), api=FakeApi(), cache=ResponseCache(), now=self.NOW)
        doc = json.loads(resp["body"])
        self.assertEqual(len(doc["times"]), 17)  # now .. +48 h every 3 h
        self.assertEqual(len(doc["aqi"][0]), air.REGION_GRID["rows"] * air.REGION_GRID["cols"])
        self.assertEqual(doc["times"][0], self.NOW.isoformat(timespec="minutes"))

    def test_cams_down(self):
        resp = handle(self.event("/air", lat="30.9", lon="75.85"), api=FakeApi(fail_air=True), cache=ResponseCache(), now=self.NOW)
        self.assertEqual(resp["statusCode"], 502)
        bad = handle(self.event("/air", lat="x", lon="75"), api=FakeApi(), cache=ResponseCache(), now=self.NOW)
        self.assertEqual(bad["statusCode"], 400)


class FireWatchEmissionTests(unittest.TestCase):
    def test_every_fire_has_type_and_emissions(self):
        from test_firewatch import DETECTIONS, snap, wind

        doc = firewatch.run(firewatch.FireWatchRequest(24), FakeApi(wind=wind(), fires=DETECTIONS),
                            now=datetime(2026, 10, 9, 18, 0, tzinfo=IST), snap=snap()).report
        fires = [f["properties"] for f in doc["features"] if f["properties"]["kind"] == "fire"]
        for f in fires:
            self.assertIn(f["fire_type"], landuse.CATEGORIES)
            if emissions.modelled(f["fire_type"]):
                self.assertGreater(f["emissions"]["kg"]["pm2_5"], 0)
                self.assertIn(f["emissions"]["toxicity"]["level"], ("low", "moderate", "high", "very high"))
        self.assertFalse([f for f in doc["features"] if f["properties"]["kind"] in ("aq_grid", "station")])
        reached = [f["properties"] for f in doc["features"] if f["properties"]["kind"] == "reached"]
        self.assertTrue(reached and all("air" not in p for p in reached))
        json.dumps(doc)


if __name__ == "__main__":
    unittest.main()
