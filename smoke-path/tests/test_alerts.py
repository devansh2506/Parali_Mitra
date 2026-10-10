"""Alerts and cases: sending, the citizen inbox, case status, who may act, and the DynamoDB store."""

import json
import os
import unittest
from datetime import datetime
from unittest import mock

import helpers  # noqa: F401 - puts src/ on the path

from smoke_path import IST, alerts, app

NOW = datetime(2026, 10, 10, 14, 0, tzinfo=IST)
PLACES = [{"name": "Rampura", "lat": 30.20, "lon": 75.80, "place_type": "village", "arrival": "2026-10-10T18:00+05:30"},
          {"name": "Bhucho", "lat": 30.25, "lon": 75.10, "place_type": "town"}]
SOURCE = {"name": "Demo Farmer 1", "contact": "+91-00000-00001", "role": "farmer", "demo": True}


def event(method, path, body=None, params=None, claims=None):
    ev = {"requestContext": {"http": {"method": method, "path": path}}, "rawPath": path, "queryStringParameters": params}
    if body is not None:
        ev["body"] = json.dumps(body)
    if claims is not None:
        ev["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}
    return ev


def public(**over):
    return {"fire_id": "30.20_75.80_20261010", "kind": "public_alert", "target": {"places": PLACES},
            "message": "Smoke is coming.", "language": "en", **over}


def source(**over):
    return {"fire_id": "30.20_75.80_20261010", "kind": "source_warning", "target": SOURCE,
            "message": "Please stop burning.", "language": "en", "fire": {"near": "Rampura", "state": "Punjab", "type": "farm"}, **over}


class Api(unittest.TestCase):
    def setUp(self):
        self.store = alerts.MemoryStore()

    def call(self, method, path, body=None, params=None, claims=None):
        r = app.handle(event(method, path, body, params, claims), store=self.store, now=NOW, notify=None)
        return r["statusCode"], json.loads(r["body"]) if r["body"] else None


class SendingTests(Api):
    def test_public_alert_reaches_the_inbox_of_people_nearby_only(self):
        status, a = self.call("POST", "/alerts", public())
        self.assertEqual(status, 201)
        self.assertEqual((a["kind"], a["language"], a["delivery"]), ("public_alert", "en", ["in-app"]))
        status, near = self.call("GET", "/alerts", params={"lat": "30.21", "lon": "75.81", "radius_km": "10"})
        self.assertEqual((status, near["count"]), (200, 1))
        self.assertEqual(near["alerts"][0]["id"], a["id"])
        self.assertLess(near["alerts"][0]["distance_km"], 3)
        self.assertNotIn("sent_by", near["alerts"][0])
        _, far = self.call("GET", "/alerts", params={"lat": "28.6", "lon": "77.2"})
        self.assertEqual(far["count"], 0)

    def test_source_warning_is_private_and_starts_the_case(self):
        self.call("POST", "/alerts", source())
        _, inbox = self.call("GET", "/alerts", params={"lat": "30.2", "lon": "75.8"})
        self.assertEqual(inbox["count"], 0)  # farmers' warnings never show in a citizen inbox
        _, log = self.call("GET", "/activity")
        self.assertEqual([a["kind"] for a in log["alerts"]], ["source_warning"])
        _, cases = self.call("GET", "/cases")
        case = cases["cases"][0]
        self.assertEqual((case["status"], case["fire"]["state"], len(case["timeline"])), ("warning_sent", "Punjab", 1))
        self.assertIn("Demo Farmer 1", case["timeline"][0]["text"])

    def test_public_alert_does_not_change_the_status(self):
        self.call("POST", "/alerts", public())
        _, cases = self.call("GET", "/cases")
        self.assertEqual(cases["cases"][0]["status"], "new")
        self.assertEqual(len(cases["cases"][0]["timeline"]), 1)

    def test_newest_first(self):
        t = [datetime(2026, 10, 10, h, 0, tzinfo=IST) for h in (10, 12)]
        for when, text in zip(t, ("first", "second")):
            alerts.create_alert(self.store, public(message=text), {}, when)
        _, r = self.call("GET", "/alerts", params={"lat": "30.2", "lon": "75.8"})
        self.assertEqual([a["message"] for a in r["alerts"]], ["second", "first"])

    def test_bad_requests_are_400_with_a_reason(self):
        for body, word in [(public(kind="spam"), "kind"), (public(message=" "), "message"), (public(fire_id="a b"), "fire_id"),
                           (public(target={"places": []}), "places"), (public(target={"places": [{"name": "x", "lat": 99, "lon": 1}]}), "lat"),
                           (public(language="fr"), "language"), (source(target={"name": "x"}), "contact"),
                           (source(target={**SOURCE, "role": "king"}), "role"), (public(message="x" * 2000), "too long")]:
            status, err = self.call("POST", "/alerts", body)
            self.assertEqual(status, 400, body)
            self.assertIn(word, err["error"])
        r = app.handle({"requestContext": {"http": {"method": "POST"}}, "rawPath": "/alerts", "body": "{not json"}, store=self.store)
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(self.call("GET", "/alerts")[0], 400)  # lat and lon are needed
        self.assertEqual(self.call("DELETE", "/alerts")[0], 405)


class CaseTests(Api):
    def test_status_flow_and_timeline(self):
        self.call("POST", "/alerts", source())
        fid = "30.20_75.80_20261010"
        status, case = self.call("PATCH", f"/cases/{fid}", {"status": "acknowledged", "note": "Owner replied"})
        self.assertEqual((status, case["status"]), (200, "acknowledged"))
        status, case = self.call("PATCH", f"/cases/{fid}", {"status": "resolved"})
        self.assertEqual(case["status"], "resolved")
        self.assertEqual([e["event"] for e in case["timeline"]], ["source_warning", "status", "status"])
        status, case = self.call("PATCH", f"/cases/{fid}", {"status": "new"})  # reopen
        self.assertEqual(case["status"], "new")

    def test_rules(self):
        fid = "c1"
        self.assertEqual(self.call("PATCH", f"/cases/{fid}", {"status": "acknowledged"})[0], 400)  # nothing to acknowledge yet
        status, err = self.call("PATCH", f"/cases/{fid}", {"status": "dismissed"})
        self.assertEqual(status, 400)
        self.assertIn("why", err["error"])
        status, case = self.call("PATCH", f"/cases/{fid}", {"status": "dismissed", "note": "Brick kiln, licensed"})
        self.assertEqual((status, case["status"]), (200, "dismissed"))
        self.assertIn("licensed", case["timeline"][-1]["text"])
        self.assertEqual(self.call("PATCH", f"/cases/{fid}", {"status": "banana"})[0], 400)
        self.assertEqual(self.call("PATCH", f"/cases/{fid}", {})[0], 400)
        status, case = self.call("PATCH", f"/cases/{fid}", {"note": "Called the officer"})
        self.assertEqual(case["timeline"][-1]["event"], "note")

    def test_url_encoded_fire_id(self):
        status, case = self.call("PATCH", "/cases/30.20_75.80_20261010", {"note": "hello"})
        self.assertEqual((status, case["fire_id"]), (200, "30.20_75.80_20261010"))


class WhoMayActTests(Api):
    ON = {"REQUIRE_AUTHORITY": "true"}

    def test_open_when_the_switch_is_off(self):
        self.assertEqual(self.call("POST", "/alerts", public())[0], 201)

    def test_authority_group_is_required_when_on(self):
        with mock.patch.dict(os.environ, self.ON):
            self.assertEqual(self.call("POST", "/alerts", public())[0], 403)  # no token at all
            self.assertEqual(self.call("POST", "/alerts", public(), claims={"email": "c@example.com", "cognito:groups": "[citizen]"})[0], 403)
            status, a = self.call("POST", "/alerts", public(), claims={"email": "officer@example.com", "cognito:groups": "[authority]"})
            self.assertEqual(status, 201)
            self.assertEqual(self.store.list_alerts()[0]["sent_by"], "officer@example.com")
            self.assertEqual(self.call("GET", "/cases")[0], 403)
            self.assertEqual(self.call("GET", "/cases", claims={"cognito:groups": ["authority"]})[0], 200)
            self.assertEqual(self.call("GET", "/activity")[0], 403)
            self.assertEqual(self.call("PATCH", "/cases/x", {"note": "n"})[0], 403)
            # the citizen inbox stays open to everyone
            self.assertEqual(self.call("GET", "/alerts", params={"lat": "30.2", "lon": "75.8"})[0], 200)

    def test_group_claim_shapes(self):
        self.assertEqual(alerts._groups({"cognito:groups": "[authority citizen]"}), ["authority", "citizen"])
        self.assertEqual(alerts._groups({"cognito:groups": "authority"}), ["authority"])
        self.assertEqual(alerts._groups({}), [])


class EmailTests(Api):
    def test_email_is_best_effort(self):
        a = alerts.create_alert(self.store, public(), {}, NOW, notify=lambda alert: True)
        self.assertEqual(a["delivery"], ["in-app", "email"])
        def boom(alert):
            raise RuntimeError("SNS down")
        b = alerts.create_alert(self.store, public(), {}, NOW, notify=boom)
        self.assertEqual(b["delivery"], ["in-app"])  # still saved and shown in the inbox
        self.assertIsNone(alerts.sns_notifier({}))
        self.assertTrue(callable(alerts.sns_notifier({"ALERTS_SNS_TOPIC": "arn:aws:sns:ap-south-1:000000000000:demo"})))


class FakeTable:
    """Just enough of a boto3 Table: put_item, get_item, query by pk."""

    def __init__(self):
        self.rows = {}

    def put_item(self, Item):
        self.rows[(Item["pk"], Item["sk"])] = dict(Item)

    def get_item(self, Key):
        row = self.rows.get((Key["pk"], Key["sk"]))
        return {"Item": row} if row else {}

    def query(self, **kwargs):
        pk = kwargs["KeyConditionExpression"]
        return {"Items": [r for (p, _), r in sorted(self.rows.items()) if p == pk]}


class DynamoStoreTests(unittest.TestCase):
    def test_same_behaviour_as_memory(self):
        store = alerts.DynamoStore(FakeTable())
        with mock.patch.object(alerts, "_key", lambda name: mock.Mock(eq=lambda v: v)):
            alerts.create_alert(store, source(), {"email": "o@example.com"}, NOW)
            alerts.create_alert(store, public(), {}, datetime(2026, 10, 10, 15, 0, tzinfo=IST))
            self.assertEqual([a["kind"] for a in store.list_alerts()], ["public_alert", "source_warning"])
            self.assertEqual(store.get_case("30.20_75.80_20261010")["status"], "warning_sent")
            alerts.update_case(store, "30.20_75.80_20261010", {"status": "acknowledged"}, {}, NOW)
            self.assertEqual([c["status"] for c in store.list_cases()], ["acknowledged"])
            self.assertEqual(len(alerts.alerts_near(store, 30.2, 75.8, 10)), 1)
        self.assertIsNone(store.get_case("nope"))


if __name__ == "__main__":
    unittest.main()
