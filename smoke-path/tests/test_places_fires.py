"""Places along the path (Overpass) and satellite fires (FIRMS)."""

import json
import unittest
from datetime import timedelta
from unittest import mock

from helpers import FIELD, START, const_series, km_east, km_north, place

from smoke_path import fires as fires_mod
from smoke_path.fires import area, fetch_fires_raw, parse_fires_csv
from smoke_path.net import ApiError
from smoke_path.places import build_query, closest_point, decode_places, locate, parse_overpass
from smoke_path.trajectory import PathPoint, cone_puffs, single_site, trace


def east_path(hours=24, speed=5):
    return trace(single_site(const_series(speed, 270)), *FIELD, START, hours)


class LocateTests(unittest.TestCase):
    """Test 6."""

    def setUp(self):
        self.path = east_path()
        self.puffs = cone_puffs(self.path)

    def test_place_36_km_downwind_arrives_after_2_hours_in_band(self):
        rampur = place("Rampur", *km_east(36))
        (p,) = locate([rampur], self.path, self.puffs)
        self.assertTrue(p["in_band"])
        self.assertLess(p["distance_km"], 0.2)
        self.assertLess(abs((p["arrival"] - (START + timedelta(hours=2))).total_seconds()), 120)

    def test_place_upwind_is_not_in_band(self):
        (p,) = locate([place("Upwind", *km_east(-10))], self.path, self.puffs)
        self.assertFalse(p["in_band"])
        self.assertEqual(p["arrival"], START)  # closest point is the field itself
        self.assertAlmostEqual(p["distance_km"], 10, delta=0.1)

    def test_place_far_to_the_side_is_not_in_band(self):
        lat, lon = km_east(36)
        side = place("Side", *km_north(30, lat, lon))  # band radius at 2 h is 1 + 0.25*36 = 10 km
        (p,) = locate([side], self.path, self.puffs)
        self.assertFalse(p["in_band"])
        self.assertAlmostEqual(p["distance_km"], 30, delta=0.2)

    def test_place_just_inside_the_band_edge(self):
        lat, lon = km_east(36)
        near = place("Near", *km_north(9, lat, lon))
        (p,) = locate([near], self.path, self.puffs)
        self.assertTrue(p["in_band"])

    def test_sorted_by_arrival(self):
        far = place("Far", *km_east(90))
        near = place("Near", *km_east(18))
        out = locate([far, near], self.path, self.puffs)
        self.assertEqual([p["name"] for p in out], ["Near", "Far"])

    def test_closest_point_uses_segments_not_just_vertices(self):
        # Two points 20 km apart; the place sits 1 km off the middle of the segment.
        a = PathPoint(START, *FIELD, 0.0)
        b_lat, b_lon = km_east(20)
        b = PathPoint(START + timedelta(hours=1), b_lat, b_lon, 20.0)
        mid_lat, mid_lon = km_east(10)
        dist, t = closest_point(*km_north(1, mid_lat, mid_lon), [a, b])
        self.assertAlmostEqual(dist, 1.0, delta=0.01)  # vertices alone would say ~10 km
        self.assertLess(abs((t - (START + timedelta(minutes=30))).total_seconds()), 30)


class OverpassTests(unittest.TestCase):
    """Test 7."""

    REPLY = {
        "version": 0.6,
        "generator": "Overpass API",
        "elements": [
            {
                "type": "node",
                "id": 807827478,
                "lat": 30.3708266,
                "lon": 75.8647369,
                "tags": {"name": "Dhuri", "name:pa": "ਧੂਰੀ", "place": "town", "population": "49406"},
            },
            {
                "type": "way",
                "id": 165067725,
                "center": {"lat": 30.2521986, "lon": 75.8365280},
                "tags": {"name": "Civil Hospital, Sangrur", "amenity": "hospital", "emergency": "yes"},
            },
            {"type": "way", "id": 1, "tags": {"name": "No position school", "amenity": "school"}},
            {"type": "node", "id": 2, "lat": 30.3, "lon": 75.9, "tags": {"amenity": "school"}},
            {
                "type": "node",
                "id": 3,
                "lat": 30.31,
                "lon": 75.91,
                "tags": {"name": "ਬਡਰੁੱਖਾਂ", "name:en": "Badrukhan", "place": "village"},
            },
            {"type": "node", "id": 4, "lat": 30.32, "lon": 75.92, "tags": {"name": "Shop", "shop": "yes"}},
        ],
    }

    def test_nodes_and_ways_are_parsed_and_unpositioned_skipped(self):
        found = parse_overpass(self.REPLY)
        names = [p["name"] for p in found]
        self.assertEqual(names, ["Dhuri", "Civil Hospital, Sangrur", "Unnamed school", "Badrukhan"])
        dhuri, hospital, school, village = found
        self.assertEqual((dhuri["lat"], dhuri["lon"]), (30.3708266, 75.8647369))
        self.assertEqual((hospital["lat"], hospital["lon"]), (30.2521986, 75.8365280))
        self.assertEqual(dhuri["place_type"], "town")
        self.assertEqual(dhuri["name_local"], "ਧੂਰੀ")
        self.assertEqual(hospital["place_type"], "hospital")
        self.assertFalse(school["named"])
        self.assertEqual(village["name"], "Badrukhan")  # name:en preferred over name
        self.assertEqual(village["name_local"], "ਬਡਰੁੱਖਾਂ")  # local-script name kept

    def test_same_place_mapped_twice_is_deduplicated(self):
        reply = {
            "elements": [
                {"type": "node", "id": 1, "lat": 30.2462, "lon": 75.8641, "tags": {"name": "GGS School", "amenity": "school"}},
                {"type": "way", "id": 2, "center": {"lat": 30.2463, "lon": 75.8642}, "tags": {"name": "GGS School", "amenity": "school"}},
            ]
        }
        self.assertEqual(len(parse_overpass(reply)), 1)

    def test_bad_reply_raises(self):
        with self.assertRaises(ApiError):
            parse_overpass({"remark": "runtime error"})
        with self.assertRaises(ApiError):
            decode_places(b"<html>Too many requests</html>")

    def test_cut_short_with_nothing_found_is_a_failure(self):
        body = b'{"elements": [], "remark": "runtime error: Query timed out in \\"query\\" at line 5 after 21 seconds."}'
        with self.assertRaises(ApiError):
            decode_places(body)

    def test_cut_short_with_some_places_keeps_them_with_a_note(self):
        body = json.dumps({"elements": self.REPLY["elements"][:2], "remark": "runtime error: Query timed out"}).encode()
        found, note = decode_places(body)
        self.assertEqual(len(found), 2)
        self.assertIn("incomplete", note)
        self.assertEqual(decode_places(json.dumps(self.REPLY).encode())[1], None)

    def test_server_timeout_in_query(self):
        self.assertIn("[timeout:20]", build_query([(30.0, 75.0), (30.1, 75.1)]))
        self.assertIn("[timeout:115]", build_query([(30.0, 75.0), (30.1, 75.1)], 115))

    def test_query_uses_path_as_line_with_three_radii(self):
        q = build_query([(30.245, 75.844), (30.245, 75.844), (30.3, 75.9)])
        self.assertTrue(q.startswith("[out:json][timeout:20];"))
        self.assertIn('node["place"~"^(city|town)$"](around:15000,30.24500,75.84400,30.30000,75.90000);', q)
        self.assertIn('node["place"="village"](around:5000,', q)
        self.assertIn('nwr["amenity"~"^(school|college|hospital|clinic)$"](around:3000,', q)
        self.assertTrue(q.endswith("out center tags;"))


# Header and a row copied from a real FIRMS VIIRS S-NPP file (Punjab, 7 Oct 2026).
REAL_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"
    "30.34445,75.78986,332.94,0.4,0.37,2026-10-07,0822,N,nominal,2.0NRT,298.27,2.72,D\n"
)
# Same data in the area-API layout (instrument column, one-letter confidence, no zero padding).
API_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "30.34445,75.78986,332.94,0.4,0.37,2026-10-07,822,N,VIIRS,n,2.0NRT,298.27,2.72,D\n"
    "29.96034,74.98039,340.39,0.39,0.36,2026-10-07,2000,N,VIIRS,h,2.0NRT,302.24,8.28,N\n"
    ",,,,,,,,,,,,,\n"
)


class NetErrorTests(unittest.TestCase):
    def test_html_error_pages_are_not_shown_to_users(self):
        import io
        import urllib.error

        from smoke_path import net

        page = b'<?xml version="1.0"?><html><body>Dispatcher_Client::timeout</body></html>'
        err = urllib.error.HTTPError("https://x", 504, "Gateway Timeout", {}, io.BytesIO(page))
        with mock.patch.object(net.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(ApiError) as ctx:
                net.request("https://x", 1, name="OpenStreetMap (Overpass)")
        self.assertEqual(str(ctx.exception), "OpenStreetMap (Overpass) answered HTTP 504: server busy")

    def test_json_reason_is_kept(self):
        import io
        import urllib.error

        from smoke_path import net

        body = b'{"error": true, "reason": "Parameter forecast_days must not exceed 16"}'
        err = urllib.error.HTTPError("https://x", 400, "Bad Request", {}, io.BytesIO(body))
        with mock.patch.object(net.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(ApiError) as ctx:
                net.request("https://x", 1, name="Open-Meteo")
        self.assertEqual(str(ctx.exception), "Open-Meteo answered HTTP 400: Parameter forecast_days must not exceed 16")


class FirmsTests(unittest.TestCase):
    """Test 8."""

    def test_real_format_row(self):
        (f,) = parse_fires_csv(REAL_CSV, "VIIRS_SNPP_NRT")
        self.assertEqual((f["lat"], f["lon"]), (30.34445, 75.78986))
        self.assertEqual(f["date"], "2026-10-07")
        self.assertEqual(f["time_utc"], "08:22")
        self.assertEqual(f["time_ist"], "1:52 pm")  # +5:30
        self.assertEqual(f["confidence"], "nominal")
        self.assertEqual(f["frp"], 2.72)
        self.assertEqual(f["source"], "VIIRS_SNPP_NRT")

    def test_api_layout_and_ist_after_midnight(self):
        found = parse_fires_csv(API_CSV, "VIIRS_NOAA20_NRT")
        self.assertEqual(len(found), 2)  # blank row skipped
        self.assertEqual(found[0]["time_utc"], "08:22")
        self.assertEqual(found[0]["confidence"], "nominal")
        self.assertEqual(found[1]["time_ist"], "1:30 am")
        self.assertEqual(found[1]["date_ist"], "2026-10-08")
        self.assertEqual(found[1]["confidence"], "high")

    def test_every_detail_is_kept_for_the_popup(self):
        found = parse_fires_csv(API_CSV, "VIIRS_NOAA21_NRT")
        f = found[0]
        self.assertEqual(f["satellite"], "NOAA-21")
        self.assertEqual(f["instrument"], "VIIRS")
        self.assertEqual(f["daynight"], "day")
        self.assertEqual((f["bright_ti4"], f["bright_ti5"]), (332.94, 298.27))
        self.assertEqual((f["scan"], f["track"]), (0.4, 0.37))
        self.assertEqual(f["version"], "2.0NRT")
        self.assertEqual(f["seen_at"], "2026-10-07T13:52+05:30")  # start time for tracing its smoke
        self.assertEqual(f["seen_text"], "1:52 pm, 7 Oct")
        self.assertEqual(found[1]["daynight"], "night")

    def test_error_text_gives_no_fires(self):
        self.assertEqual(parse_fires_csv("Invalid MAP_KEY.", "VIIRS_SNPP_NRT"), [])
        self.assertEqual(parse_fires_csv("", "VIIRS_SNPP_NRT"), [])
        header_only = REAL_CSV.split("\n")[0] + "\n"
        self.assertEqual(parse_fires_csv(header_only, "VIIRS_SNPP_NRT"), [])

    def test_area_is_longitude_first(self):
        self.assertEqual(area(30.245, 75.844), "74.84,29.25,76.84,31.25")

    def test_fetch_rejects_text_reply_and_hides_key(self):
        with mock.patch.object(fires_mod, "request", return_value=b"Invalid MAP_KEY SECRETKEY123."):
            with self.assertRaises(ApiError) as ctx:
                fetch_fires_raw("VIIRS_SNPP_NRT", *FIELD, "SECRETKEY123")
        self.assertNotIn("SECRETKEY123", str(ctx.exception))
        with mock.patch.object(fires_mod, "request", side_effect=ApiError("failed for SECRETKEY123")):
            with self.assertRaises(ApiError) as ctx:
                fetch_fires_raw("VIIRS_SNPP_NRT", *FIELD, "SECRETKEY123")
        self.assertNotIn("SECRETKEY123", str(ctx.exception))

    def test_fetch_url_shape(self):
        with mock.patch.object(fires_mod, "request", return_value=REAL_CSV.encode()) as req:
            fetch_fires_raw("VIIRS_NOAA21_NRT", *FIELD, "KEY")
        url = req.call_args[0][0]
        self.assertEqual(
            url,
            "https://firms.modaps.eosdis.nasa.gov/api/area/csv/KEY/VIIRS_NOAA21_NRT/74.84,29.25,76.84,31.25/1",
        )


if __name__ == "__main__":
    unittest.main()
