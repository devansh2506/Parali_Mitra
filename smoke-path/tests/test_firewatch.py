"""Fire watch: NASA fires -> merged fires -> smoke paths -> villages, schools and hospitals reached."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from helpers import DAY0, FIELD, NOW, FakeApi, const_series, km_east, km_north

from smoke_path import IST, app, firewatch
from smoke_path.firewatch import FireWatchRequest, cluster, strength, summarise
from smoke_path.snapshot import Snapshot
from smoke_path.trajectory import WindGrid
from smoke_path.wind import WindSeries


def det(lat, lon, seen, frp=5.0, satellite="NOAA-20", source="VIIRS_NOAA20_NRT", confidence="nominal"):
    t = datetime.fromisoformat(seen)
    return {
        "lat": lat, "lon": lon, "seen_at": t.isoformat(timespec="minutes"),
        "seen_text": f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}, {t.day} {t.strftime('%b')}",
        "date": t.date().isoformat(), "time_utc": "00:00", "time_ist": "", "date_ist": t.date().isoformat(),
        "confidence": confidence, "frp": frp, "bright_ti4": 330.0, "bright_ti5": 295.0, "scan": 0.4, "track": 0.4,
        "satellite": satellite, "instrument": "VIIRS", "daynight": "day", "version": "2.0NRT", "source": source,
    }


def at(km_e, km_n):
    lat, lon = km_east(km_e)
    return km_north(km_n, lat, lon)


B = at(0, 2)  # fire B: 2 km north of the field, seen 9 Oct 1:30 pm
A = FIELD  # fire A: at the field, seen 10 Oct 1:30 am by two satellites
DETECTIONS = [
    det(*B, "2026-10-09T13:30+05:30", frp=12.0, satellite="Suomi NPP", source="VIIRS_SNPP_NRT", confidence="high"),
    det(*A, "2026-10-10T01:30+05:30", frp=4.0),
    det(*at(0.3, 0), "2026-10-10T02:10+05:30", frp=2.0, satellite="NOAA-21", source="VIIRS_NOAA21_NRT"),
]


def row(name, point, ptype, osm):
    return [round(point[0], 5), round(point[1], 5), ptype, name, "", osm]


PLACES = [
    row("Home", at(-2, 0), "village", "n1"),  # 2 km upwind: near both fires, but behind the smoke
    row("Shared Village", at(36, 1), "village", "n2"),  # on both paths (1 km from each)
    row("Only A Village", at(36, -4), "village", "n3"),  # 4 km from A's path, 6 km from B's (village limit 5 km)
    row("B School", at(18, 4), "school", "n4"),  # 2 km from B's path, 4 km from A's (school limit 3 km)
    row("Big Town", at(54, 12), "town", "n5"),  # 12 km from A, 10 km from B (town limit 15 km)
]
ALL_TILES = [[i, j] for i in range(56, 66) for j in range(146, 168)]  # far enough east for 432 km paths


def snap(tiles=ALL_TILES):
    return Snapshot({"format": 1, "tile_deg": 0.5, "tiles": tiles, "osm_base": "2026-10-09T00:00:00Z", "places": PLACES})


def wind():
    return const_series(5, 270, n=96, t0=DAY0 - timedelta(days=1))  # 9 Oct 00:00 .. 12 Oct 23:00


def run(api=None, **kw):
    api = api or FakeApi(wind=wind(), fires=DETECTIONS)
    kw.setdefault("snap", snap())
    return firewatch.run(FireWatchRequest(hours=24), api, now=NOW, **kw), api


def kind(doc, k):
    return [f for f in doc["features"] if f["properties"]["kind"] == k]


class ClusterTests(unittest.TestCase):
    def test_same_fire_seen_by_two_satellites_is_one_fire(self):
        groups = cluster(DETECTIONS)
        self.assertEqual(sorted(len(g) for g in groups), [1, 2])

    def test_far_apart_or_hours_apart_are_separate_fires(self):
        base = det(*FIELD, "2026-10-10T13:30+05:30")
        far = det(*at(3, 0), "2026-10-10T13:35+05:30")
        later = det(*FIELD, "2026-10-11T01:30+05:30")
        self.assertEqual(len(cluster([base, far, later])), 3)

    def test_chain_across_grid_cells(self):
        dets = [det(*at(0.8 * k, 0), "2026-10-10T13:30+05:30") for k in range(4)]  # 0.8 km steps
        self.assertEqual(len(cluster(dets)), 1)

    def test_summary_of_one_fire(self):
        group = sorted(DETECTIONS[1:], key=lambda d: d["seen_at"])
        fire = summarise(group)
        self.assertEqual(fire["detections"], 2)
        self.assertEqual(fire["seen_at"], "2026-10-10T01:30+05:30")  # first time seen
        self.assertEqual(fire["satellites"], ["NOAA-20", "NOAA-21"])
        self.assertAlmostEqual(fire["frp_sum"], 6.0)
        self.assertEqual(fire["strength"], "medium")
        lon_weighted = (4 * A[1] + 2 * at(0.3, 0)[1]) / 6  # FRP-weighted
        self.assertAlmostEqual(fire["lon"], lon_weighted, places=9)
        self.assertEqual(len(fire["details"]), 2)
        self.assertEqual((strength(None), strength(1), strength(5), strength(15)), (None, "small", "medium", "large"))


class WindGridTests(unittest.TestCase):
    def test_bilinear_and_clamped(self):
        times = [DAY0 + timedelta(hours=h) for h in range(3)]
        # u grows 1 m/s per node to the east, v grows 2 m/s per node to the north.
        series = [WindSeries(times, [float(c)] * 3, [2.0 * r] * 3) for r in range(3) for c in range(3)]
        grid = WindGrid(30.0, 75.0, 0.5, 3, 3, series)
        u, v = grid.at(DAY0, 30.25, 75.75)  # halfway between nodes
        self.assertAlmostEqual(u, 1.5)
        self.assertAlmostEqual(v, 1.0)
        self.assertEqual(grid.at(DAY0, 10.0, 99.0), (2.0, 0.0))  # outside: nearest edge
        self.assertEqual(len(WindGrid.points(24.0, 69.75, 0.75, 17, 17)), 289)


class FireWatchRunTests(unittest.TestCase):
    def setUp(self):
        self.result, self.api = run()
        self.doc = self.result.report

    def test_fires_and_paths(self):
        fires = kind(self.doc, "fire")
        self.assertEqual([f["properties"]["id"] for f in fires], ["F1", "F2"])  # numbered by time first seen
        f1, f2 = (f["properties"] for f in fires)
        self.assertEqual((f1["seen_at"], f1["detections"], f1["strength"]), ("2026-10-09T13:30+05:30", 1, "large"))
        self.assertEqual((f2["detections"], f2["satellites"]), (2, ["NOAA-20", "NOAA-21"]))
        self.assertEqual((f1["near"], f2["near"]), ("Home", "Home"))
        self.assertTrue(f1["traced"])
        paths = kind(self.doc, "fire_path")
        self.assertEqual(len(paths), 2)
        p1 = paths[0]["properties"]
        self.assertEqual(len(paths[0]["geometry"]["coordinates"]), 25)
        self.assertEqual(p1["times"][0], "2026-10-09T13:30+05:30")
        self.assertAlmostEqual(p1["km"][1], 18.0, places=3)

    def test_one_wind_request_for_all_fires_with_past_hours(self):
        forecasts = [c for c in self.api.calls if c[0] == "forecast"]
        self.assertEqual(len(forecasts), 1)
        self.assertEqual(len(forecasts[0][1]), 289)
        self.assertEqual(self.api.past_days, 1)  # the first fire was seen yesterday
        self.assertEqual(self.api.count("fires_box"), 3)  # one per satellite

    def test_places_reached_and_by_how_many_fires(self):
        reached = {f["properties"]["name"]: f["properties"] for f in kind(self.doc, "reached")}
        self.assertEqual(
            {n: p["fires"] for n, p in reached.items()},
            {"Shared Village": 2, "Big Town": 2, "B School": 1, "Only A Village": 1},
        )  # "Home" is upwind: never inside the smoke band
        self.assertEqual(reached["Shared Village"]["near_town"], "Big Town")  # within 25 km
        self.assertEqual(reached["Big Town"]["near_town"], "")  # towns are not "near" themselves
        shared = reached["Shared Village"]
        first = datetime.fromisoformat(shared["first_arrival"])  # B + 2 h (36 km at 18 km/h)
        self.assertLess(abs((first - datetime(2026, 10, 9, 15, 30, tzinfo=IST)).total_seconds()), 120)
        self.assertEqual([fid for fid, _ in shared["arrivals"]], ["F1", "F2"])
        stats = self.doc["stats"]
        self.assertEqual((stats["fires"], stats["detections"]), (2, 3))
        self.assertEqual(stats["reached"], {"village": 2, "town": 1, "school": 1})
        self.assertEqual(sum(stats["fire_types"].values()), 2)
        fires = {f["properties"]["id"]: f["properties"] for f in kind(self.doc, "fire")}
        self.assertEqual((fires["F1"]["places_reached"], fires["F2"]["places_reached"]), (3, 3))

    def test_summary(self):
        self.assertEqual(
            [line for line in self.doc["summary"] if not line.startswith(("What was burning", "Most smoke", "Worst air"))],
            [
                "NASA satellites saw 2 fires in and around Punjab and Haryana in the last day (3 satellite detections).",
                "Their smoke will likely reach 2 villages, 1 town and 1 school or college.",
                "Shared Village (village): smoke from 2 fires, since about 3:30 pm (9 Oct).",
                "Big Town (town): smoke from 2 fires, since about 4:30 pm (9 Oct).",
                "B School (school): smoke from 1 fire, since about 2:30 pm (9 Oct).",
            ],
        )
        self.assertTrue(self.doc["summary"][1].startswith("What was burning: "))
        self.assertTrue(self.doc["summary"][-1].startswith("Worst air on a smoke path: "))
        self.assertEqual(self.doc["notes"], ["No monitoring-station key (OPENAQ_API_KEY): the forecast is not corrected by measurements."])
        self.assertTrue(self.result.cacheable)
        json.dumps(self.doc)

    def test_future_arrival_says_from(self):
        early = datetime(2026, 10, 9, 14, 0, tzinfo=IST)  # "now" before the smoke reaches the villages
        doc = firewatch.run(FireWatchRequest(24), FakeApi(wind=wind(), fires=DETECTIONS), now=early, snap=snap()).report
        self.assertEqual(doc["summary"][3], "Shared Village (village): smoke from 2 fires, from about 3:30 pm.")


class SameAnswerAsTheMapTests(unittest.TestCase):
    def test_exposure_uses_the_path_exactly_as_sent(self):
        doc = run()[0].report
        path = kind(doc, "fire_path")[0]
        for lon, lat in path["geometry"]["coordinates"]:
            self.assertEqual((round(lat, 5), round(lon, 5)), (lat, lon))
        self.assertTrue(all(round(k, 3) == k for k in path["properties"]["km"]))

    def test_arrivals_are_listed_in_time_order(self):
        # Two fires seen at the same minute, 12 km apart north-south, a town halfway: both reach it.
        dets = [det(*at(0, 6), "2026-10-10T13:30+05:30"), det(*at(0, -6), "2026-10-10T13:30+05:30")]
        mid = Snapshot({"format": 1, "tile_deg": 0.5, "tiles": ALL_TILES, "osm_base": None,
                        "places": [row("Middle Town", at(30, 0), "town", "n9")]})
        doc = firewatch.run(FireWatchRequest(24), FakeApi(wind=wind(), fires=dets), now=NOW, snap=mid).report
        (place,) = kind(doc, "reached")
        times = [t for _, t in place["properties"]["arrivals"]]
        self.assertEqual(len(times), 2)
        self.assertEqual(times, sorted(times))


class FireWatchProblemTests(unittest.TestCase):
    def test_no_fires(self):
        result, api = run(FakeApi(wind=wind(), fires=[]))
        self.assertEqual(result.report["summary"], ["No fires were seen by NASA satellites in and around Punjab and Haryana in the last day."])
        self.assertEqual(api.count("forecast"), 0)  # no wind needed

    def test_no_key(self):
        with self.assertRaises(firewatch.NoFiresKey):
            run(FakeApi(wind=wind(), fires=DETECTIONS, fires_key=False))

    def test_all_satellites_fail(self):
        with self.assertRaises(firewatch.FiresUnavailable):
            run(FakeApi(wind=wind(), fires=DETECTIONS, fail_fires=True))

    def test_one_satellite_fails(self):
        api = FakeApi(wind=wind(), fires=DETECTIONS)
        original = api.fires_box

        def flaky(source, box, days):
            if source == "VIIRS_NOAA21_NRT":
                raise firewatch.ApiError("NASA FIRMS VIIRS_NOAA21_NRT answered HTTP 503: server busy")
            return original(source, box, days)

        api.fires_box = flaky
        result, _ = run(api)
        self.assertIn("Some satellite fire data is missing (VIIRS_NOAA21_NRT).", result.report["notes"])
        self.assertFalse(result.cacheable)

    def test_wind_fails(self):
        with self.assertRaises(firewatch.WindUnavailable):
            run(FakeApi(wind=wind(), fires=DETECTIONS, fail_wind=True))

    def test_no_saved_places(self):
        result, _ = run(snap=None)
        doc = result.report
        self.assertEqual(kind(doc, "reached"), [])
        self.assertIn("Villages, schools and hospitals could not be checked (no saved places).", doc["notes"])
        self.assertEqual(doc["summary"][2], "Villages, schools and hospitals on their smoke paths could not be checked right now.")

    def test_paths_leaving_the_saved_area(self):
        result, _ = run(snap=snap(tiles=[[60, 151]]))
        self.assertIn("Some smoke paths leave the saved area; places there are not checked here.", result.report["notes"])

    def test_fire_outside_the_wind_forecast(self):
        short = const_series(5, 270, n=72, t0=DAY0)  # starts 10 Oct: fire B (9 Oct) cannot be traced
        result, _ = run(FakeApi(wind=short, fires=DETECTIONS))
        fires = {f["properties"]["id"]: f["properties"] for f in kind(result.report, "fire")}
        self.assertFalse(fires["F1"]["traced"])
        self.assertTrue(fires["F2"]["traced"])
        self.assertIn("1 fire could not be traced (outside the wind forecast).", result.report["notes"])


class FiresEndpointTests(unittest.TestCase):
    def event(self, **params):
        return {"rawPath": "/fires", "queryStringParameters": params or None,
                "requestContext": {"http": {"method": "GET", "path": "/fires"}}}

    def test_route_and_cache(self):
        cache = app.ResponseCache()
        api = FakeApi(wind=wind(), fires=DETECTIONS)
        from unittest import mock

        with mock.patch.object(firewatch.snapshot, "get", return_value=snap()):
            r1 = app.handle(self.event(hours="24"), api=api, cache=cache, now=NOW)
            r2 = app.handle(self.event(hours="24"), api=api, cache=cache, now=NOW)
        self.assertEqual(r1["statusCode"], 200)
        self.assertEqual(json.loads(r1["body"])["view"], "fires")
        self.assertEqual(r1["body"], r2["body"])
        self.assertEqual(api.count("forecast"), 1)  # second answer came from the cache
        self.assertEqual(r1["headers"]["Access-Control-Allow-Origin"], "*")

    def test_large_replies_are_gzipped_for_browsers(self):
        import base64
        import gzip
        from unittest import mock

        api = FakeApi(wind=wind(), fires=DETECTIONS)
        ev = self.event(hours="24")
        ev["headers"] = {"accept-encoding": "gzip, deflate, br"}
        with mock.patch.object(firewatch.snapshot, "get", return_value=snap()), mock.patch.object(app, "GZIP_MIN_BYTES", 100):
            resp = app.handle(ev, api=api, cache=app.ResponseCache(), now=NOW)
            plain = app.handle(self.event(hours="24"), api=api, cache=app.ResponseCache(), now=NOW)
        self.assertTrue(resp["isBase64Encoded"])
        self.assertEqual(resp["headers"]["Content-Encoding"], "gzip")
        doc = json.loads(gzip.decompress(base64.b64decode(resp["body"])))
        self.assertEqual(doc["view"], "fires")
        self.assertFalse(plain["isBase64Encoded"])  # no Accept-Encoding: plain JSON
        self.assertNotIn("Content-Encoding", plain["headers"])

    def test_errors(self):
        no_key = app.handle(self.event(), api=FakeApi(wind=wind(), fires_key=False), cache=app.ResponseCache(), now=NOW)
        self.assertEqual(no_key["statusCode"], 503)
        down = app.handle(self.event(), api=FakeApi(wind=wind(), fires=DETECTIONS, fail_fires=True), cache=app.ResponseCache(), now=NOW)
        self.assertEqual(down["statusCode"], 502)
        bad = app.handle(self.event(hours="99"), api=FakeApi(), cache=app.ResponseCache(), now=NOW)
        self.assertEqual(bad["statusCode"], 400)

    def test_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fire_watch_sample.json"
            path.write_text(json.dumps({"type": "FeatureCollection", "view": "fires", "features": [], "sample": False}))
            resp = app.handle(self.event(sample="true"), fire_sample_path=path)
            self.assertIs(json.loads(resp["body"])["sample"], True)
            missing = app.handle(self.event(sample="true"), fire_sample_path=Path(tmp) / "none.json")
            self.assertEqual(missing["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
