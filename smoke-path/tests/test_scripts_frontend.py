"""Local server routing, sample embedding, and the map page. No network, no sockets."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

import _env  # noqa: E402
import local_server  # noqa: E402
import save_fixtures  # noqa: E402

MAP = (ROOT / "frontend" / "map.html").read_text(encoding="utf-8")
FIXTURE_SAMPLE = ROOT / "fixtures" / "sample_response.json"
PACKAGE_SAMPLE = ROOT / "src" / "smoke_path" / "sample_response.json"


class LocalServerTests(unittest.TestCase):
    def test_root_redirects_to_live_map(self):
        status, headers, _ = local_server.route("GET", "/")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "/map.html?api=/smoke")

    def test_map_is_served(self):
        status, headers, body = local_server.route("GET", "/map.html?api=/smoke")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b'id="sample-data"', body)

    def test_smoke_goes_through_the_handler(self):
        status, headers, body = local_server.route("GET", "/smoke?lat=abc&lon=75")
        self.assertEqual(status, 400)  # rejected before any network call
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("lat", json.loads(body)["error"])

    def test_unknown_path(self):
        self.assertEqual(local_server.route("GET", "/secrets.env")[0], 404)

    def test_event_shape(self):
        ev = local_server.make_event("GET", "/smoke", "lat=30.2&lon=75.8&x=1&x=2")
        self.assertEqual(ev["queryStringParameters"], {"lat": "30.2", "lon": "75.8", "x": "1,2"})
        self.assertEqual(ev["requestContext"]["http"]["method"], "GET")


class SampleEmbedTests(unittest.TestCase):
    def test_embed_round_trip_is_html_safe(self):
        doc = {"type": "FeatureCollection", "summary": ["</script><b>x</b> & "], "features": []}
        html = save_fixtures.embed_sample(MAP, doc)
        block = re.search(r'<script id="sample-data" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("<", block)
        self.assertNotIn(">", block)
        self.assertEqual(save_fixtures.embedded_sample(html), doc)
        # Re-embedding replaces, it does not append.
        again = save_fixtures.embed_sample(html, {"x": 1})
        self.assertEqual(save_fixtures.embedded_sample(again), {"x": 1})
        self.assertEqual(again.count('id="sample-data"'), 1)

    def test_saved_sample_matches_everywhere(self):
        if not FIXTURE_SAMPLE.exists():
            self.skipTest("no sample yet: run scripts/save_fixtures.py")
        fixture = json.loads(FIXTURE_SAMPLE.read_text(encoding="utf-8"))
        packaged = json.loads(PACKAGE_SAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(fixture, packaged, "src/smoke_path/sample_response.json is out of date")
        self.assertEqual(save_fixtures.embedded_sample(MAP), fixture, "frontend/map.html sample is out of date")
        kinds = {f["properties"]["kind"] for f in fixture["features"]}
        self.assertTrue({"field", "path", "puff"} <= kinds)
        self.assertEqual(fixture["label"], "Likely smoke direction")


COMPLETE = '{"elements": [{"type": "node", "id": 1, "lat": 30.3, "lon": 75.9, "tags": {"place": "village", "name": "A"}}]}'
CUT_SHORT = '{"elements": [], "remark": "runtime error: Query timed out in \\"query\\" at line 5"}'


def make_capture(folder, overpass, label):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "forecast_field.json").write_text(label)
    (folder / "forecast_multi.json").write_text(label)
    (folder / "overpass.json").write_text(overpass)
    (folder / "firms_VIIRS_SNPP_NRT.csv").write_text("latitude,longitude\n" + label)


class AdoptCaptureTests(unittest.TestCase):
    """A new capture must never make the saved sample worse."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.new, self.fix = root / "_new", root / "fixtures"
        self.meta = {"lat": 30.2, "lon": 75.8, "start": "2026-10-10T14:00+05:30", "hours": 24, "saved_at": "NEW"}

    def tearDown(self):
        self.tmp.cleanup()

    def old_capture(self, overpass):
        make_capture(self.fix, overpass, "old")
        (self.fix / "meta.json").write_text(json.dumps(dict(self.meta, saved_at="OLD")))

    def test_complete_new_capture_replaces_everything(self):
        self.old_capture(COMPLETE)
        make_capture(self.new, COMPLETE, "new")
        self.assertEqual(save_fixtures.adopt(self.new, self.fix, self.meta), "all")
        self.assertEqual((self.fix / "forecast_field.json").read_text(), "new")
        self.assertEqual(json.loads((self.fix / "meta.json").read_text())["saved_at"], "NEW")

    def test_busy_osm_keeps_old_path_and_places_but_takes_new_fires(self):
        self.old_capture(COMPLETE)
        make_capture(self.new, CUT_SHORT, "new")
        self.assertEqual(save_fixtures.adopt(self.new, self.fix, self.meta), "fires_only")
        self.assertEqual((self.fix / "forecast_field.json").read_text(), "old")
        self.assertEqual((self.fix / "overpass.json").read_text(), COMPLETE)
        self.assertTrue((self.fix / "firms_VIIRS_SNPP_NRT.csv").read_text().endswith("new"))
        meta = json.loads((self.fix / "meta.json").read_text())
        self.assertEqual((meta["saved_at"], meta["fires_saved_at"]), ("OLD", "NEW"))

    def test_no_good_old_capture_takes_the_new_one(self):
        make_capture(self.new, CUT_SHORT, "new")
        self.fix.mkdir()
        self.assertEqual(save_fixtures.adopt(self.new, self.fix, self.meta), "all")
        self.assertEqual((self.fix / "forecast_field.json").read_text(), "new")
        self.assertFalse(save_fixtures.places_complete(self.fix))


class EnvFileTests(unittest.TestCase):
    def test_reads_values_and_never_overrides_the_shell(self):
        import os
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text('# comment\nFIRMS_MAP_KEY="abc123"\nexport WIND_LEVEL=80m  # note\nOVERPASS_URL=from-file\nbad line\n')
            with mock.patch.dict(os.environ, {"OVERPASS_URL": "from-shell"}, clear=False):
                os.environ.pop("FIRMS_MAP_KEY", None)
                os.environ.pop("WIND_LEVEL", None)
                loaded = _env.load_env(env)
                self.assertEqual(sorted(loaded), ["FIRMS_MAP_KEY", "WIND_LEVEL"])
                self.assertEqual(os.environ["FIRMS_MAP_KEY"], "abc123")
                self.assertEqual(os.environ["WIND_LEVEL"], "80m")
                self.assertEqual(os.environ["OVERPASS_URL"], "from-shell")
            self.assertEqual(_env.load_env(Path(tmp) / "missing.env"), [])


class MapPageTests(unittest.TestCase):
    def test_uses_leaflet_194_from_cdnjs_and_osm_tiles(self):
        self.assertIn("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", MAP)
        self.assertIn("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css", MAP)
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", MAP)
        self.assertIn("openstreetmap.org/copyright", MAP)

    def test_label_controls_and_escaping(self):
        self.assertIn("Likely smoke direction", MAP)
        self.assertIn('type="datetime-local"', MAP)
        self.assertIn('<option value="24">', MAP)
        self.assertIn('<option value="48">', MAP)
        self.assertIn("Show smoke path", MAP)
        self.assertIn("Hours after burning", MAP)
        self.assertIn("function esc(", MAP)
        self.assertIn("Sample data", MAP)
        # OSM names only reach HTML through esc() or textContent.
        for m in re.finditer(r"p\.name\b", MAP):
            line = MAP[MAP.rfind("\n", 0, m.start()) : MAP.find("\n", m.end())]
            self.assertIn("esc(", line, f"unescaped name in: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
