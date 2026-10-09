"""Fire type, CPCB AQI, the CAMS grid, the smoke plume, stations and GET /air. No network."""

import json
import math
import unittest
from datetime import datetime, timedelta

from helpers import DAY0, FakeApi, GRID_T0, const_grid, const_series

from smoke_path import IST, air, airquality, app, firewatch, landuse, plume, stations
from smoke_path.airquality import FieldGrid, aqi, averages, category, parse_hourly_points, sub_index
from smoke_path.app import ResponseCache, handle
from smoke_path.trajectory import PathPoint


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

    def test_grid_spec_is_cams_aligned_and_bounded(self):
        s = airquality.grid_spec([(30.25, 75.85), (31.1, 76.9)])
        self.assertAlmostEqual(s["south"] / 0.4, round(s["south"] / 0.4))
        self.assertLessEqual(s["south"], 30.05)
        self.assertGreaterEqual(s["south"] + (s["rows"] - 1) * s["step"], 31.3)
        big = airquality.grid_spec([(20, 65), (36, 85)])
        self.assertLessEqual(big["rows"] * big["cols"], airquality.MAX_AQ_POINTS)

    def test_aq_url_has_all_variables(self):
        url = airquality.aq_url([(30.0, 75.4), (30.4, 75.8)], 3, 3)
        self.assertIn("latitude=30,30.4", url)
        self.assertIn("domains=cams_global", url)
        for v in airquality.VARIABLES:
            self.assertIn(v, url)


class PlumeTests(unittest.TestCase):
    def test_emission_from_frp(self):
        r = plume.rates_from_frp(10, "farm")
        self.assertAlmostEqual(r["pm2_5"], 10 * 0.368 * 6.26)
        self.assertAlmostEqual(r["no2"], 10 * 0.368 * 3.11 * 46 / 30)
        self.assertIsNone(plume.rates_from_frp(10, "industrial"))  # not modelled
        self.assertIsNone(plume.rates_from_frp(None, "farm"))

    def test_emission_from_field_size(self):
        self.assertAlmostEqual(plume.burned_tonnes(5), 5 * 0.404686 * 6.3 * 0.8)
        r = plume.rates_from_area(5)
        self.assertAlmostEqual(r["pm2_5"] * 3600 / 1000, plume.burned_tonnes(5) * 6.26)  # kg over the hour

    def test_hand_computed_concentration(self):
        # Neutral (D), 5 km downwind on the centre line, 3 m/s, mixing height 1000 m.
        q, x = 10.0, 5000.0
        sy = math.hypot(0.08 * x / math.sqrt(1 + 0.0001 * x), (1 + 0.25 * 5) * 1000 / 2)
        sz = 0.06 * x / math.sqrt(1 + 0.0015 * x)
        expected = q / (math.sqrt(2 * math.pi) * 3 * sy * math.sqrt(math.pi / 2) * sz) * 1e6
        self.assertAlmostEqual(plume.concentration(q, 5, 0, 3, 1000, "D"), expected)

    def test_mixing_height_traps_smoke(self):
        night = plume.concentration(10, 40, 0, 3, 100, "F")
        day = plume.concentration(10, 40, 0, 3, 1500, "B")
        self.assertGreater(night, 3 * day)
        self.assertLess(plume.concentration(10, 40, 0, 3, 100, "F"), plume.concentration(10, 20, 0, 3, 100, "F"))
        self.assertLess(plume.concentration(10, 20, 8, 3, 500, "D"), plume.concentration(10, 20, 0, 3, 500, "D"))

    def test_stability_classes(self):
        self.assertEqual(plume.stability(1.5, 700, 0), "A")
        self.assertEqual(plume.stability(4, 400, 0), "C")
        self.assertEqual(plume.stability(7, 700, 0), "C")
        self.assertEqual(plume.stability(2, 0, 10), "F")
        self.assertEqual(plume.stability(4, 0, 80), "D")

    def test_hours_are_spread_over_bins(self):
        out = {}
        plume.add_hours(out, DAY0, DAY0 + timedelta(minutes=30), 1.0, 10.0)
        self.assertEqual(out, {0: 5.0, 1: 5.0})


def ctx_with(api=None, now=DAY0 + timedelta(hours=14)):
    api = api or FakeApi()
    spec = {"south": 29.6, "west": 75.2, "step": 0.4, "rows": 4, "cols": 4}
    return air.prepare(api, now, spec, spec)


def straight_path(lat=30.245, lon=75.844, start=DAY0 + timedelta(hours=12), hours=6, kmh=18.0):
    """Due east at kmh."""
    pts = []
    for i in range(hours * 4 + 1):
        km = kmh * i / 4
        pts.append(PathPoint(start + timedelta(minutes=15 * i), lat, lon + km / (111.32 * math.cos(math.radians(lat))), km))
    return pts


class AirContextTests(unittest.TestCase):
    def test_plume_adds_smoke_downwind_only(self):
        ctx = ctx_with()
        path = straight_path()
        src = air.Source("F1", path, plume.rates_from_frp(20, "farm"), path[0].t)
        on = ctx.extra(path[8].lat, path[8].lon, [src])  # 36 km downwind
        off = ctx.extra(path[8].lat + 0.5, path[8].lon, [src])  # 55 km to the side
        self.assertGreater(sum(on["pm2_5"].values()), 1)
        self.assertEqual(off, {})
        hour = max(on["pm2_5"], key=on["pm2_5"].get)
        self.assertEqual(ctx.aq.t0 + timedelta(hours=hour), DAY0 + timedelta(hours=14))  # arrives 2 h later
        base = ctx.at(path[8].lat, path[8].lon, DAY0 + timedelta(hours=14))
        smoky = ctx.at(path[8].lat, path[8].lon, DAY0 + timedelta(hours=14), on)
        self.assertGreater(smoky["pm2_5"], base["pm2_5"])
        self.assertEqual(base["pm2_5"], 60.0)
        self.assertEqual((base["aqi"], base["category"]), (100, "satisfactory"))  # PM2.5 60 and PM10 100 -> 100

    def test_no_weather_means_no_plume_but_still_aqi(self):
        ctx = ctx_with(FakeApi(fail_met=True))
        self.assertIsNone(ctx.met)
        self.assertTrue(any("could not be estimated" in n for n in ctx.notes))
        path = straight_path()
        self.assertEqual(ctx.extra(path[8].lat, path[8].lon, [air.Source("F1", path, plume.rates_from_frp(20, "farm"), path[0].t)]), {})
        self.assertIsNotNone(ctx.at(30.2, 75.9, DAY0 + timedelta(hours=14)))

    def test_no_cams_raises(self):
        with self.assertRaises(air.AirUnavailable):
            ctx_with(FakeApi(fail_air=True))

    def test_station_correction(self):
        reading = {"id": 1, "name": "Ludhiana", "provider": "CPCB", "lat": 30.9, "lon": 75.85,
                   "time": DAY0 + timedelta(hours=13), "pm2_5": 120.0, "pm10": None}
        api = FakeApi(stations=[reading])
        spec = {"south": 30.4, "west": 75.6, "step": 0.4, "rows": 3, "cols": 3}
        ctx = air.prepare(api, DAY0 + timedelta(hours=14), spec, spec)
        self.assertEqual(ctx.factors, [{"lat": 30.9, "lon": 75.85, "pm2_5": 2.0}])
        self.assertAlmostEqual(ctx.correction(30.9, 75.85)["pm2_5"], 2.0)
        self.assertEqual(ctx.correction(30.9, 75.85)["pm10"], 1.0)  # no PM10 reading
        self.assertEqual(ctx.correction(32.0, 75.85)["pm2_5"], 1.0)  # > 75 km away
        self.assertEqual(ctx.at(30.9, 75.85, DAY0 + timedelta(hours=14))["pm2_5"], 120.0)
        self.assertTrue(ctx.info()["corrected"])

    def test_overlay_and_outlook(self):
        ctx = ctx_with()
        o = ctx.overlay()
        self.assertEqual(len(o["times"]), len(air.OVERLAY_HOURS))
        self.assertEqual(len(o["aqi"][0]), 16)
        self.assertEqual(len(ctx.outlook(30.2, 75.9)), 48)


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

    def test_late_readings_up_to_three_days(self):
        loc = stations.parse_locations(self.locations(), self.NOW)[0]
        two_days = {"results": [{"datetime": {"utc": "2026-10-07T12:00:00Z"}, "value": 70, "sensorsId": 11}]}
        four_days = {"results": [{"datetime": {"utc": "2026-10-05T12:00:00Z"}, "value": 70, "sensorsId": 11}]}
        self.assertEqual(stations.parse_latest(two_days, loc, self.NOW)["pm2_5"], 70.0)  # OpenAQ's CPCB copy lags ~2 days
        self.assertIsNone(stations.parse_latest(four_days, loc, self.NOW))

    def test_factor_is_clamped(self):
        spec = {"south": 30.4, "west": 75.6, "step": 0.4, "rows": 3, "cols": 3}
        grid = const_grid(spec, {"pm2_5": 100.0, "pm10": 100.0})
        far_off = [{"lat": 30.9, "lon": 75.85, "time": GRID_T0 + timedelta(hours=60), "pm2_5": 5.0, "pm10": 900.0}]
        self.assertEqual(stations.factors(far_off, grid), [{"lat": 30.9, "lon": 75.85, "pm2_5": 0.2, "pm10": 5.0}])

    def test_key_is_never_shown(self):
        from unittest import mock

        from smoke_path.net import ApiError

        with mock.patch.object(stations, "request", side_effect=ApiError("failed for https://x?k=SECRET123")):
            with self.assertRaises(ApiError) as caught:
                stations.fetch_locations_raw((30, 75, 31, 76), "SECRET123")
        self.assertNotIn("SECRET123", str(caught.exception))

    def test_correction_fades_with_distance(self):
        f = [{"lat": 30.0, "lon": 75.0, "pm2_5": 3.0}]
        self.assertAlmostEqual(stations.correction_at(30.0, 75.0, f, "pm2_5"), 3.0)
        mid = stations.correction_at(30.0 + 37.5 / 111.32, 75.0, f, "pm2_5")
        self.assertAlmostEqual(mid, 2.0, places=2)
        self.assertEqual(stations.correction_at(31.0, 75.0, f, "pm2_5"), 1.0)


class FireWatchAirTests(unittest.TestCase):
    def test_fire_type_and_air_in_the_reply(self):
        from test_firewatch import DETECTIONS, snap, wind

        doc = firewatch.run(firewatch.FireWatchRequest(24), FakeApi(wind=wind(), fires=DETECTIONS),
                            now=datetime(2026, 10, 9, 18, 0, tzinfo=IST), snap=snap()).report
        fires = [f["properties"] for f in doc["features"] if f["properties"]["kind"] == "fire"]
        for f in fires:
            self.assertIn(f["fire_type"], landuse.CATEGORIES)
            self.assertTrue(f["fire_type_reason"])
        reached = [f["properties"] for f in doc["features"] if f["properties"]["kind"] == "reached"]
        self.assertTrue(all(p["air"] and p["air"]["aqi"] > 0 for p in reached))
        grid = [f for f in doc["features"] if f["properties"]["kind"] == "aq_grid"][0]["properties"]
        self.assertEqual(len(grid["aqi"][0]), firewatch.AIR_GRID["rows"] * firewatch.AIR_GRID["cols"])
        self.assertTrue(doc["air"]["fire_plumes"])
        json.dumps(doc)

    def test_cams_failure_keeps_the_fire_watch(self):
        from test_firewatch import DETECTIONS, snap, wind

        r = firewatch.run(firewatch.FireWatchRequest(24), FakeApi(wind=wind(), fires=DETECTIONS, fail_air=True),
                          now=datetime(2026, 10, 9, 18, 0, tzinfo=IST), snap=snap())
        self.assertFalse(r.cacheable)
        self.assertIsNone(r.report["air"])
        self.assertTrue(any("Air quality could not be predicted" in n for n in r.report["notes"]))
        self.assertTrue(any(f["properties"]["kind"] == "reached" for f in r.report["features"]))


class AirEndpointTests(unittest.TestCase):
    def event(self, path, **q):
        return {"rawPath": path, "requestContext": {"http": {"method": "GET", "path": path}}, "queryStringParameters": q}

    def test_outlook_for_a_spot(self):
        from test_firewatch import DETECTIONS, wind

        firewatch._last.clear()
        api = FakeApi(wind=wind(), fires=DETECTIONS)
        now = datetime(2026, 10, 9, 18, 0, tzinfo=IST)
        cache = ResponseCache()
        resp = handle(self.event("/air", lat="30.4", lon="76.2"), api=api, cache=cache, now=now)
        self.assertEqual(resp["statusCode"], 200)
        doc = json.loads(resp["body"])
        self.assertEqual(len(doc["outlook"]), 48)
        self.assertEqual(doc["now"]["t"], "2026-10-09T18:00+05:30")
        self.assertIsNotNone(cache.get(("fires", 24, app.wind_level())))  # the fire watch it built is reused
        again = handle(self.event("/air", lat="30.4", lon="76.2"), api=FakeApi(fail_air=True), cache=cache, now=now)
        self.assertEqual(again["body"], resp["body"])  # cached

    def test_bad_input(self):
        resp = handle(self.event("/air", lat="abc", lon="76"), api=FakeApi(), cache=ResponseCache())
        self.assertEqual(resp["statusCode"], 400)

    def test_smoke_parameters(self):
        now = datetime(2026, 10, 10, 9, 0, tzinfo=IST)
        base = {"lat": "30.245", "lon": "75.844", "start": "2026-10-10T14:00"}
        self.assertEqual(app.parse_request(base, now).acres, 5.0)
        self.assertEqual(app.parse_request(dict(base, acres="12.5"), now).acres, 12.5)
        for bad in ({"acres": "0"}, {"acres": "1000"}, {"fire_type": "volcano"}, {"frp": "-1"}):
            with self.assertRaises(app.BadRequest):
                app.parse_request(dict(base, **bad), now)


if __name__ == "__main__":
    unittest.main()


class OpenMeteoLimitTests(unittest.TestCase):
    def test_retries_once_after_429_and_limits_concurrency(self):
        import threading
        from unittest import mock

        from smoke_path import net
        from smoke_path.net import ApiError

        calls = []
        with mock.patch.object(net, "request", side_effect=[ApiError("Open-Meteo answered HTTP 429: busy"), b"ok"]), \
                mock.patch.object(net, "RETRY_429_S", 0):
            self.assertEqual(net.request_open_meteo("https://x", 1), b"ok")
        with mock.patch.object(net, "request", side_effect=ApiError("Open-Meteo answered HTTP 500")) as req:
            with self.assertRaises(ApiError):
                net.request_open_meteo("https://x", 1)
            self.assertEqual(req.call_count, 1)  # only 429 is retried

        busy, peak, lock = [0], [0], threading.Lock()

        def slow(*a, **k):
            with lock:
                busy[0] += 1
                peak[0] = max(peak[0], busy[0])
            import time as _t
            _t.sleep(0.02)
            with lock:
                busy[0] -= 1
            calls.append(1)
            return b"ok"

        with mock.patch.object(net, "request", side_effect=slow):
            threads = [threading.Thread(target=net.request_open_meteo, args=("https://x", 1)) for _ in range(9)]
            [t.start() for t in threads]
            [t.join() for t in threads]
        self.assertEqual(len(calls), 9)
        self.assertLessEqual(peak[0], 3)


class EmissionTests(unittest.TestCase):
    def test_per_hour_from_frp(self):
        from smoke_path import emissions

        e = emissions.from_frp(5, "farm")
        burned = 0.368 * 5 * 3600  # kg of straw an hour
        self.assertEqual(e["burned_kg"], round(burned))
        self.assertAlmostEqual(e["kg"]["pm2_5"], round(burned * 6.26 / 1000, 1))
        self.assertAlmostEqual(e["kg"]["no2"], round(burned * 3.11 * 46 / 30 / 1000, 1))
        self.assertEqual(e["table"], "AGRI")
        self.assertIsNone(emissions.from_frp(5, "industrial"))
        self.assertEqual(emissions.from_frp(5, "forest")["table"], "TEMF")

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
        self.assertAlmostEqual(f["kg"]["pm2_5"], round(plume.burned_tonnes(5) * 6.26, 1))
