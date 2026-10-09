"""Option B: the saved places snapshot, the snapshot-first lookup and the build script."""

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FIELD, ROOT, km_east, km_north

sys.path.insert(0, str(ROOT / "scripts"))

import build_places_snapshot as builder  # noqa: E402

from smoke_path import apis, snapshot  # noqa: E402
from smoke_path.net import ApiError  # noqa: E402
from smoke_path.places import find_places  # noqa: E402
from smoke_path.snapshot import Snapshot, distance_to_line_km, tile_of  # noqa: E402

# A straight line 60 km east from the field (hourly points every 12 km).
LINE = [km_east(12 * k) for k in range(6)]


def row(name, lat, lon, ptype, osm, local=""):
    return [round(lat, 5), round(lon, 5), ptype, name, local, osm]


def make_doc(rows, tiles=None):
    if tiles is None:  # all tiles around the field: lat 29-32, lon 74-78
        tiles = [[i, j] for i in range(58, 64) for j in range(148, 156)]
    return {"format": 1, "tile_deg": 0.5, "tiles": tiles, "osm_base": "2026-10-09T00:00:00Z", "places": rows}


def at(km_e, km_n):
    lat, lon = km_east(km_e)
    return km_north(km_n, lat, lon)


ROWS = [
    row("Near Village", *at(20, 3), "village", "n1", "ਨੇੜੇ"),  # 3 km off the line: in (village limit 5 km)
    row("Far Village", *at(20, 7), "village", "n2"),  # 7 km: out
    row("Big Town", *at(30, 12), "town", "n3"),  # 12 km: in (town limit 15 km)
    row("", *at(40, 2.5), "school", "w4"),  # unnamed school 2.5 km: in (amenity limit 3 km)
    row("Hospital", *at(40, 4), "hospital", "n5"),  # 4 km: out
    row("Behind Village", *at(-4, 0), "village", "n6"),  # 4 km behind the field: in (closest point = field)
]


class SnapshotLookupTests(unittest.TestCase):
    def setUp(self):
        self.snap = Snapshot(make_doc(ROWS))

    def test_type_specific_distances(self):
        found = self.snap.near(LINE)
        self.assertEqual(sorted(p["osm"] for p in found), ["n1", "n3", "n6", "w4"])
        school = next(p for p in found if p["osm"] == "w4")
        self.assertEqual((school["name"], school["named"]), ("Unnamed school", False))
        village = next(p for p in found if p["osm"] == "n1")
        self.assertEqual((village["name"], village["name_local"], village["place_type"]), ("Near Village", "ਨੇੜੇ", "village"))

    def test_same_shape_as_overpass_places(self):
        found = self.snap.near(LINE)[0]
        self.assertEqual(set(found), {"name", "name_local", "place_type", "named", "lat", "lon", "osm"})

    def test_coverage_needs_every_tile_within_reach(self):
        self.assertTrue(self.snap.covers(*FIELD))
        holey = Snapshot(make_doc(ROWS, tiles=[[60, 151]]))  # one tile: 30.0-30.5, 75.5-76.0
        self.assertTrue(holey.covers(*FIELD))  # its 15 km reach (75.69-75.9997) stays inside the tile
        self.assertFalse(holey.covers(30.245, 75.95))  # 15 km east of this is the missing tile
        self.assertTrue(holey.covers(30.245, 75.95, margin_km=1))

    def test_distance_to_line_uses_segments(self):
        mid = at(6, 1)  # 1 km off the middle of the first 12 km segment
        self.assertAlmostEqual(distance_to_line_km(*mid, LINE[:2]), 1.0, delta=0.01)
        self.assertEqual(tile_of(30.245, 75.844, 0.5), (60, 151))

    def test_wrong_format_is_rejected(self):
        with self.assertRaises(ValueError):
            Snapshot(dict(make_doc(ROWS), format=99))


class FindPlacesTests(unittest.TestCase):
    def setUp(self):
        self.snap = Snapshot(make_doc(ROWS))
        self.calls = []

    def fetch(self, reply=None, error=None):
        def fetch_raw(line, timeout):
            self.calls.append(list(line))
            if error:
                raise error
            return json.dumps(reply or {"elements": []}).encode()

        return fetch_raw

    def test_covered_path_never_calls_overpass(self):
        found, note = find_places(LINE, 15, self.fetch(), self.snap)
        self.assertEqual(self.calls, [])
        self.assertIsNone(note)
        self.assertEqual(len(found), 4)

    def test_path_leaving_the_saved_area_asks_overpass_for_that_part_only(self):
        tiles = [[i, j] for i in range(58, 64) for j in range(148, 152)]  # east edge at lon 76.0
        snap = Snapshot(make_doc(ROWS, tiles))
        line = [km_east(20 * k) for k in range(8)]  # 0..140 km east, crosses lon 76.0
        live_reply = {
            "elements": [
                {"type": "node", "id": 9, "lat": line[-1][0], "lon": line[-1][1], "tags": {"name": "Live Town", "place": "town"}},
                {"type": "node", "id": 1, "lat": ROWS[0][0], "lon": ROWS[0][1], "tags": {"name": "Near Village", "place": "village"}},
            ]
        }
        found, note = find_places(line, 15, self.fetch(live_reply), snap)
        self.assertIsNone(note)
        (asked,) = self.calls
        first_out = next(k for k, pt in enumerate(line) if not snap.covers(*pt))
        self.assertEqual(asked, line[first_out - 1 :])  # from the last covered point on
        names = [p["name"] for p in found]
        self.assertIn("Live Town", names)
        self.assertEqual(names.count("Near Village"), 1)  # merged without duplicates

    def test_overpass_failure_outside_keeps_saved_places_with_a_note(self):
        snap = Snapshot(make_doc(ROWS, [[i, j] for i in range(58, 64) for j in range(148, 152)]))
        line = [km_east(20 * k) for k in range(8)]
        found, note = find_places(line, 15, self.fetch(error=ApiError("OpenStreetMap (Overpass) answered HTTP 504: server busy")), snap)
        self.assertTrue(found)
        self.assertEqual(note, "Places outside the saved area could not be checked (OpenStreetMap (Overpass) answered HTTP 504: server busy).")

    def test_without_a_snapshot_everything_goes_to_overpass(self):
        reply = {"elements": [{"type": "node", "id": 7, "lat": 30.3, "lon": 75.9, "tags": {"name": "X", "place": "village"}}]}
        found, note = find_places(LINE, 15, self.fetch(reply), None)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual([p["osm"] for p in found], ["n7"])

    def test_live_api_uses_the_shipped_snapshot(self):
        api = apis.LiveApi()
        with mock.patch.object(snapshot, "get", return_value=self.snap), mock.patch.object(
            apis.places, "fetch_places_raw", side_effect=AssertionError("no network expected")
        ):
            found, note = api.places(LINE, 15)
        self.assertEqual(len(found), 4)
        self.assertIsNone(note)


class SnapshotFileTests(unittest.TestCase):
    def test_missing_or_broken_file_falls_back_to_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(snapshot.get(Path(tmp) / "none.json.gz"))
            bad = Path(tmp) / "bad.json.gz"
            bad.write_bytes(b"not gzip")
            with self.assertLogs("smoke_path.snapshot", level="WARNING"):
                self.assertIsNone(snapshot.get(bad))

    def test_shipped_snapshot(self):
        if not snapshot.SNAPSHOT_PATH.exists():
            self.skipTest("no snapshot yet: run scripts/build_places_snapshot.py")
        snap = Snapshot.load()
        self.assertGreater(len(snap.rows), 1000)
        self.assertTrue(snap.covers(*FIELD), "the demo field must be covered")
        self.assertEqual(len({r[5] for r in snap.rows}), len(snap.rows), "osm ids are unique")
        found = snap.near([FIELD, km_east(18)])
        self.assertTrue(any(p["place_type"] == "village" for p in found))


class BuildScriptTests(unittest.TestCase):
    def setUp(self):
        no_net = mock.patch.object(builder, "request", side_effect=AssertionError("network used in a test"))
        no_net.start()
        self.addCleanup(no_net.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.out = Path(self.tmp.name) / "places_snapshot.json.gz"
        patcher = mock.patch.object(builder, "CACHE", self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def tile_reply(self, i, j, extra=()):
        lat, lon = i * 0.5 + 0.25, j * 0.5 + 0.25
        els = [
            {"type": "node", "id": i * 1000 + j, "lat": lat, "lon": lon, "tags": {"name": f"V{i}_{j}", "place": "village"}},
            {"type": "way", "id": 42, "center": {"lat": 30.5, "lon": 76.0}, "tags": {"amenity": "school"}},  # on 4 tiles
        ] + list(extra)
        return json.dumps({"osm3s": {"timestamp_osm_base": f"2026-10-09T0{j % 10}:00:00Z"}, "elements": els}).encode()

    def test_tiles_cover_the_box(self):
        tiles = builder.tiles_in((27.5, 72.5, 33.0, 78.5))
        self.assertEqual(len(tiles), 11 * 12)
        self.assertIn((60, 151), tiles)  # the demo field's tile

    def test_reads_overpass_status_page(self):
        free = "Connected as: 1\nRate limit: 2\n2 slots available now.\nCurrently running queries:"
        busy = "Rate limit: 2\nSlot available after: 2026-10-09T10:00:05Z, in 37 seconds.\nSlot available after: 2026-10-09T10:00:50Z, in 82 seconds."
        self.assertEqual(builder.slot_wait_s(free), 0)
        self.assertEqual(builder.slot_wait_s(busy), 37)
        self.assertIsNone(builder.slot_wait_s("<html>"))
        waits = []
        with mock.patch("builtins.print"):
            builder.wait_for_slot(lambda: busy, waits.append)
        self.assertEqual(waits, [38])

    def test_punjab_tiles_come_first(self):
        tiles = builder.tiles_in((27.5, 72.5, 33.0, 78.5))
        first = sorted(tiles, key=builder.priority)[0]
        self.assertEqual(first, (61, 151))  # 30.5-31.0 N, 75.5-76.0 E (Ludhiana area)

    def test_retries_busy_tiles_and_resumes(self):
        attempts = {}

        def fetch(i, j):
            attempts[(i, j)] = attempts.get((i, j), 0) + 1
            if (i, j) == (60, 151) and attempts[(i, j)] < 3:
                raise ApiError("server busy")
            if (i, j) == (60, 152):
                raise ApiError("server busy")  # never works
            return self.tile_reply(i, j)

        tiles = [(60, 151), (60, 152), (61, 151)]
        with mock.patch("builtins.print"):
            failed = builder.download(tiles, fetch=fetch, sleep=lambda s: None, status=lambda: "2 slots available now.",
                                      fetch_split=fetch)
        self.assertEqual(failed, [(60, 152)])
        self.assertEqual(attempts[(60, 151)], 3)
        self.assertEqual(attempts[(60, 152)], 1 + len(builder.WAITS_S))
        with mock.patch("builtins.print"):
            builder.download(tiles, fetch=fetch, sleep=lambda s: None, status=lambda: "2 slots available now.",
                             fetch_split=fetch)  # second run
        self.assertEqual(attempts[(60, 151)], 3)

    def test_hard_tile_is_fetched_as_four_quarters(self):
        calls = []

        def fetch(i, j):
            calls.append("whole")
            raise ApiError("server busy")

        def fetch_split(i, j):
            calls.append("quarters")
            return self.tile_reply(i, j)

        with mock.patch("builtins.print"):
            failed = builder.download([(61, 155)], fetch=fetch, sleep=lambda s: None,
                                      status=lambda: "2 slots available now.", fetch_split=fetch_split)
        self.assertEqual(failed, [])
        self.assertEqual(calls, ["whole"] * builder.SPLIT_AFTER + ["quarters"])
        self.assertTrue(builder.cache_file(61, 155).exists())

    def test_quarters_are_merged_without_duplicates(self):
        def quarter(query):
            # Every quarter returns its own node plus one way that crosses all four quarters.
            south = float(query.split("[bbox:")[1].split(",")[0])
            west = float(query.split("[bbox:")[1].split(",")[1])
            return json.dumps({"osm3s": {"timestamp_osm_base": f"2026-10-09T0{int(west * 4) % 10}:00:00Z"}, "elements": [
                {"type": "node", "id": int(south * 1000 + west * 10), "lat": south + 0.1, "lon": west + 0.1, "tags": {"name": "Q", "place": "village"}},
                {"type": "way", "id": 7, "center": {"lat": 30.75, "lon": 76.25}, "tags": {"amenity": "hospital"}},
            ]}).encode()

        merged = json.loads(builder.fetch_tile_split(61, 152, fetch=quarter))
        self.assertEqual(len(merged["elements"]), 5)  # 4 nodes + the shared way once
        self.assertEqual(merged["split"], 4)
        self.assertTrue(merged["osm3s"]["timestamp_osm_base"].startswith("2026-10-09T"))
        q = builder.box_query(30.5, 76.0, 30.75, 76.25)
        self.assertIn("[bbox:30.500,76.000,30.750,76.250]", q)

    def test_build_merges_tiles_and_loads_back(self):
        self.cache.mkdir()
        for t in [(60, 151), (61, 151)]:
            builder.cache_file(*t).write_bytes(self.tile_reply(*t))
        rows, used = builder.build([(60, 151), (61, 151), (62, 151)], out=self.out)
        self.assertEqual(used, [[60, 151], [61, 151]])  # the missing tile is not claimed as covered
        self.assertEqual(sorted(r[5] for r in rows), ["n60151", "n61151", "w42"])  # the shared way once
        unnamed = next(r for r in rows if r[5] == "w42")
        self.assertEqual(unnamed[3], "")
        snap = Snapshot.load(self.out)
        self.assertEqual(snap.tiles, {(60, 151), (61, 151)})
        self.assertEqual(snap.osm_base, "2026-10-09T01:00:00Z")
        first = self.out.read_bytes()
        builder.build([(60, 151), (61, 151)], out=self.out)
        with gzip.open(self.out, "rt") as fh:
            created_again = json.load(fh)["created"]
        self.assertTrue(first.startswith(b"\x1f\x8b"))
        self.assertTrue(created_again)


if __name__ == "__main__":
    unittest.main()
