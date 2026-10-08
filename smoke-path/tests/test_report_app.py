"""The full report and the Lambda handler (tests 5, 10, 11 and more)."""

import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from helpers import FIELD, NOW, START, FakeApi, const_series, km_east, place

from smoke_path import IST, app
from smoke_path.pipeline import SmokeRequest, run
from smoke_path.report import arrival_text, fmt_day, fmt_time, summary


def event(**params):
    q = {"lat": str(FIELD[0]), "lon": str(FIELD[1]), "start": "2026-10-10T14:00", "hours": "24"}
    q.update({k: v for k, v in params.items() if v is not None})
    for k in [k for k, v in params.items() if v is None]:
        q.pop(k, None)
    return {
        "version": "2.0",
        "rawPath": "/smoke",
        "queryStringParameters": q,
        "requestContext": {"http": {"method": "GET", "path": "/smoke"}},
    }


def call(api, cache=None, **params):
    resp = app.handle(event(**params), api=api, cache=cache or app.ResponseCache(), now=NOW)
    return resp, json.loads(resp["body"]) if resp["body"] else None


def features(doc, kind):
    return [f for f in doc["features"] if f["properties"]["kind"] == kind]


# Places along a 5 m/s west wind (18 km per hour). Names are made up for tests.
PLACES = [
    place("Farmgate", *km_east(1)),  # reached in under 15 minutes: the farm itself
    place("Badal", *km_east(18)),  # 3:00 pm
    place("Govt School Rampur", *km_east(36), "school"),  # 4:00 pm
    place("Sangrur", *km_east(54), "town"),  # 5:00 pm
    place("Civil Hospital", *km_east(72), "hospital"),  # 6:00 pm
    place("Upwind Village", *km_east(-20)),  # not in band
]
FIRES = [
    {
        "lat": 30.34445,
        "lon": 75.78986,
        "date": "2026-10-07",
        "time_utc": "08:22",
        "time_ist": "1:52 pm",
        "date_ist": "2026-10-07",
        "confidence": "nominal",
        "frp": 2.72,
    }
]


class FullReportTests(unittest.TestCase):
    """Test 10."""

    def setUp(self):
        self.api = FakeApi(places=PLACES, fires=FIRES)
        self.resp, self.doc = call(self.api)

    def test_status_cors_and_json(self):
        self.assertEqual(self.resp["statusCode"], 200)
        self.assertEqual(self.resp["headers"]["Access-Control-Allow-Origin"], "*")
        self.assertIn("application/json", self.resp["headers"]["Content-Type"])
        json.dumps(self.doc)  # serialisable both ways

    def test_shape(self):
        doc = self.doc
        self.assertEqual(doc["type"], "FeatureCollection")
        self.assertEqual(doc["label"], "Likely smoke direction")
        self.assertEqual(doc["wind_level"], "120m")
        self.assertIs(doc["sample"], False)
        self.assertEqual(doc["uncertainty"], "cone")
        self.assertEqual(len(features(doc, "field")), 1)
        self.assertEqual(features(doc, "field")[0]["properties"]["start"], "2026-10-10T14:00+05:30")
        (path,) = features(doc, "path")
        self.assertEqual(path["geometry"]["type"], "LineString")
        self.assertEqual(len(path["geometry"]["coordinates"]), 97)
        self.assertAlmostEqual(path["properties"]["km"], 432.0, delta=0.5)
        self.assertEqual(features(doc, "member"), [])
        for f in doc["features"]:
            self.assertIn(f["geometry"]["type"], ("Point", "LineString"))
            lon, lat = (f["geometry"]["coordinates"] if f["geometry"]["type"] == "Point" else f["geometry"]["coordinates"][0])
            self.assertTrue(70 < lon < 90 and 25 < lat < 35, "coordinates must be [lon, lat]")

    def test_25_puffs_for_24_hours(self):
        puffs = features(self.doc, "puff")
        self.assertEqual(len(puffs), 25)
        self.assertEqual(puffs[0]["properties"]["hour"], 0)
        self.assertEqual(puffs[0]["properties"]["time"], "2:00 pm")
        self.assertEqual(puffs[0]["properties"]["radius_km"], 1.0)
        self.assertEqual(puffs[2]["properties"]["time"], "4:00 pm")
        self.assertEqual(puffs[10]["properties"]["time"], "12:00 am")
        self.assertEqual(puffs[10]["properties"]["day"], "11 Oct")

    def test_summary_has_right_places_and_times(self):
        self.assertEqual(
            self.doc["summary"],
            [
                "If you burn on 10 Oct at 2:00 pm, smoke will likely reach:",
                "Badal (village) by about 3:00 pm",
                "Govt School Rampur (school) by about 4:00 pm",
                "Civil Hospital (hospital) by about 6:00 pm",
            ],
        )

    def test_place_features(self):
        by_name = {f["properties"]["name"]: f["properties"] for f in features(self.doc, "place")}
        self.assertEqual(len(by_name), 6)
        school = by_name["Govt School Rampur"]
        self.assertTrue(school["in_band"])
        self.assertEqual(school["arrival_text"], "4:00 pm")
        self.assertTrue(school["arrival"].startswith("2026-10-10T1"))
        self.assertEqual(school["place_type"], "school")
        self.assertFalse(by_name["Upwind Village"]["in_band"])
        arrivals = [f["properties"]["arrival"] for f in features(self.doc, "place")]
        self.assertEqual(arrivals, sorted(arrivals))

    def test_fire_features_from_each_source(self):
        fires = features(self.doc, "fire")
        self.assertEqual(len(fires), 3)
        props = fires[0]["properties"]
        for key in ("date", "time_utc", "time_ist", "confidence", "frp", "source"):
            self.assertIn(key, props)
        self.assertEqual(self.doc["notes"], [])

    def test_two_open_meteo_calls_second_with_sampled_points(self):
        forecasts = [c for c in self.api.calls if c[0] == "forecast"]
        self.assertEqual(len(forecasts), 2)
        self.assertEqual(len(forecasts[0][1]), 1)
        self.assertEqual(len(forecasts[1][1]), 9)  # field + hours 3, 6, ..., 24
        self.assertEqual(self.api.count("ensemble"), 0)
        (places_call,) = [c for c in self.api.calls if c[0] == "places"]
        self.assertEqual(len(places_call[1]), 25)  # hourly path points as the line


class SummaryTextTests(unittest.TestCase):
    def test_no_places_message(self):
        lines = summary(START, [])
        self.assertEqual(
            lines,
            ["If you burn on 10 Oct at 2:00 pm, the smoke will likely not pass any listed village, school or hospital."],
        )

    def test_next_day_arrival_shows_the_day(self):
        start = datetime(2026, 10, 10, 22, 0, tzinfo=IST)
        self.assertEqual(arrival_text(start + timedelta(hours=3, minutes=1), start), "1:00 am (11 Oct)")

    def test_rounds_to_5_minutes(self):
        self.assertEqual(arrival_text(START + timedelta(minutes=137), START), "4:15 pm")
        self.assertEqual(arrival_text(START + timedelta(minutes=133), START), "4:15 pm")

    def test_time_and_day_format(self):
        self.assertEqual(fmt_time(datetime(2026, 10, 9, 0, 5, tzinfo=IST)), "12:05 am")
        self.assertEqual(fmt_time(datetime(2026, 10, 9, 12, 0, tzinfo=IST)), "12:00 pm")
        self.assertEqual(fmt_day(datetime(2026, 10, 9, 14, 0, tzinfo=IST)), "9 Oct")

    def test_incomplete_places_never_claim_no_places(self):
        line = summary(START, [], places_checked=False)
        self.assertEqual(len(line), 1)
        self.assertIn("could not be checked", line[0])
        found = [{"name": "Badal", "named": True, "place_type": "village", "arrival": START + timedelta(hours=1), "in_band": True}]
        self.assertEqual(summary(START, found, places_checked=False)[1], "Badal (village) by about 3:00 pm")

    def test_unnamed_place_label(self):
        p = {
            "name": "Unnamed school",
            "named": False,
            "place_type": "school",
            "arrival": START + timedelta(hours=1),
            "in_band": True,
        }
        self.assertEqual(summary(START, [p])[1], "Unnamed school by about 3:00 pm")

    def test_only_three_places_schools_and_hospitals_first(self):
        located = [
            {"name": f"V{i}", "named": True, "place_type": "village", "arrival": START + timedelta(hours=i), "in_band": True}
            for i in range(1, 6)
        ] + [
            {"name": "H", "named": True, "place_type": "hospital", "arrival": START + timedelta(hours=9), "in_band": True},
            {"name": "C", "named": True, "place_type": "clinic", "arrival": START + timedelta(hours=8), "in_band": False},
        ]
        located.sort(key=lambda p: p["arrival"])
        lines = summary(START, located)
        self.assertEqual(lines[1:], ["V1 (village) by about 3:00 pm", "V2 (village) by about 4:00 pm", "H (hospital) by about 11:00 pm"])


class HandlerErrorTests(unittest.TestCase):
    def test_start_outside_forecast_returns_400(self):
        """Test 5 (handler part): the fake forecast ends 12 Oct 11 pm."""
        resp, doc = call(FakeApi(), start="2026-10-12T20:00")
        self.assertEqual(resp["statusCode"], 400)
        self.assertIn("forecast", doc["error"])
        self.assertEqual(resp["headers"]["Access-Control-Allow-Origin"], "*")

    def test_bad_inputs_return_400(self):
        cases = [
            {"lat": None},
            {"lon": "abc"},
            {"lat": "95"},
            {"lat": "nan"},
            {"hours": "0"},
            {"hours": "49"},
            {"hours": "2.5"},
            {"start": "10/10/2026 2pm"},
            {"start": "2026-10-01T14:00"},  # in the past
            {"start": "2026-11-20T14:00"},  # beyond 16 days
            {"uncertainty": "plume"},
        ]
        for params in cases:
            with self.subTest(params=params):
                resp, doc = call(FakeApi(), **params)
                self.assertEqual(resp["statusCode"], 400)
                self.assertTrue(doc["error"])

    def test_wind_failure_returns_502(self):
        resp, doc = call(FakeApi(fail_wind=True))
        self.assertEqual(resp["statusCode"], 502)
        self.assertIn("Wind forecast unavailable", doc["error"])

    def test_unexpected_error_returns_500_without_details(self):
        api = FakeApi()
        api.forecast = lambda *a: (_ for _ in ()).throw(RuntimeError("secret internals"))
        with self.assertLogs("smoke_path.app", level="ERROR"):
            resp, doc = call(api)
        self.assertEqual(resp["statusCode"], 500)
        self.assertNotIn("secret", doc["error"])

    def test_options_preflight(self):
        ev = event()
        ev["requestContext"]["http"]["method"] = "OPTIONS"
        resp = app.handle(ev, api=FakeApi(), cache=app.ResponseCache(), now=NOW)
        self.assertEqual(resp["statusCode"], 204)
        self.assertEqual(resp["headers"]["Access-Control-Allow-Origin"], "*")

    def test_default_start_is_next_full_hour_ist(self):
        req = app.parse_request({"lat": "30", "lon": "75"}, now=datetime(2026, 10, 10, 9, 41, tzinfo=IST))
        self.assertEqual(req.start, datetime(2026, 10, 10, 10, 0, tzinfo=IST))
        self.assertEqual(req.hours, 24)
        self.assertEqual(req.uncertainty, "cone")


class PartialFailureTests(unittest.TestCase):
    """Test 11: places or fires failing still gives 200 with a note."""

    def test_places_fail(self):
        resp, doc = call(FakeApi(places=PLACES, fail_places=True))
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(features(doc, "place"), [])
        self.assertTrue(any(n.startswith("Places unavailable") for n in doc["notes"]))
        self.assertEqual(len(features(doc, "puff")), 25)
        # Never claim "no places" when places could not be checked.
        self.assertEqual(len(doc["summary"]), 1)
        self.assertNotIn("not pass", doc["summary"][0])
        self.assertIn("could not be checked", doc["summary"][0])

    def test_fires_fail(self):
        resp, doc = call(FakeApi(fires=FIRES, fail_fires=True))
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(features(doc, "fire"), [])
        self.assertTrue(any(n.startswith("Fires unavailable") for n in doc["notes"]))

    def test_both_fail(self):
        resp, doc = call(FakeApi(fail_places=True, fail_fires=True))
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(len(doc["notes"]), 2)

    def test_no_firms_key(self):
        resp, doc = call(FakeApi(fires_key=False))
        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("Fires unavailable: no NASA FIRMS key is set (FIRMS_MAP_KEY).", doc["notes"])

    def test_refine_fails_uses_field_wind(self):
        resp, doc = call(FakeApi(fail_refine=True))
        self.assertEqual(resp["statusCode"], 200)
        self.assertTrue(any("wind at your field only" in n for n in doc["notes"]))

    def test_ensemble_fails_falls_back_to_cone(self):
        resp, doc = call(FakeApi(), uncertainty="ensemble")
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(doc["uncertainty"], "cone")
        self.assertTrue(any("ensemble" in n for n in doc["notes"]))

    def test_ensemble_success(self):
        members = [const_series(5, d) for d in (250, 260, 270, 280, 290)]
        resp, doc = call(FakeApi(ensemble=members), uncertainty="ensemble")
        self.assertEqual(doc["uncertainty"], "ensemble")
        self.assertEqual(len(features(doc, "member")), 5)
        self.assertEqual(len(features(doc, "puff")), 25)
        self.assertGreater(features(doc, "puff")[12]["properties"]["radius_km"], 10)

    def test_slow_places_hit_the_time_budget(self):
        api = FakeApi(places=PLACES, places_delay=1.5)
        req = SmokeRequest(*FIELD, START, 24)
        t0 = time.monotonic()
        result = run(req, api, now=NOW, budget_s=0.3)
        self.assertLess(time.monotonic() - t0, 1.2)
        self.assertIn("Places unavailable: OpenStreetMap took too long to answer.", result.report["notes"])
        self.assertFalse(result.cacheable)


class CacheAndSampleTests(unittest.TestCase):
    def test_second_request_uses_cache(self):
        cache = app.ResponseCache()
        api = FakeApi()
        call(api, cache=cache)
        call(api, cache=cache, lat="30.2496")  # rounds to the same 0.01 cell (30.25)
        self.assertEqual(api.count("forecast"), 2)  # only the first request called the API

    def test_failed_parts_are_not_cached(self):
        cache = app.ResponseCache()
        api = FakeApi(fail_places=True)
        call(api, cache=cache)
        call(api, cache=cache)
        self.assertEqual(api.count("forecast"), 4)

    def test_cache_expires_after_30_minutes(self):
        clock = [0.0]
        cache = app.ResponseCache(clock=lambda: clock[0])
        cache.put("k", "v")
        clock[0] = 29 * 60
        self.assertEqual(cache.get("k"), "v")
        clock[0] = 30 * 60
        self.assertIsNone(cache.get("k"))

    def test_sample_true_returns_saved_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample_response.json"
            path.write_text(json.dumps({"type": "FeatureCollection", "features": [], "sample": False}))
            resp = app.handle({"queryStringParameters": {"sample": "true"}}, api=FakeApi(), sample_path=path)
            self.assertEqual(resp["statusCode"], 200)
            self.assertIs(json.loads(resp["body"])["sample"], True)
            missing = app.handle({"queryStringParameters": {"sample": "true"}}, sample_path=Path(tmp) / "nope.json")
            self.assertEqual(missing["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
