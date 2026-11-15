"""Tests for the F-001 feasibility core (``percival_core.bring_to_me``).

Run with either:
    python3 -m unittest discover -s tests -v
    python3 -m pytest            (if pytest is available)

Unit tests run entirely against a stubbed Atlas transport; all fixtures
are synthetic. One live integration test exercises the real Transit
Atlas server when one is reachable (``PERCIVAL_ATLAS_URL``, default
``http://127.0.0.1:8000``) and skips cleanly when it is not.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from percival_core import bring_to_me as btm  # noqa: E402
from percival_core.bring_to_me import (  # noqa: E402
    AtlasClient,
    AtlasUnavailable,
    FriendRef,
    HomeRef,
    NotInnerTierError,
    assess_visit,
    draft_outreach,
)

FRIEND = FriendRef("Fixture Friend", "pvta:5101")
HOME = HomeRef("hartford:6")
WHEN = datetime(2026, 11, 17, 8, 0)  # a Tuesday, inside all service periods


def _coverage_rows(pvta_status="imported", pvta_in_period=True):
    return [
        {"feed": "cttransit", "status": "imported",
         "in_service_period": True, "start": "20260830", "end": "20270109"},
        {"feed": "hartford", "status": "imported",
         "in_service_period": True, "start": "20261005", "end": "20271004"},
        {"feed": "pvta", "status": pvta_status,
         "in_service_period": pvta_in_period,
         "start": "20261102", "end": "20261219"},
    ]


def _journey(dep, arr, headsign="New Haven"):
    return {
        "found": True,
        "departure": dep,
        "arrival": arr,
        "legs": [{
            "kind": "transit", "from_stop": "a:1", "to_stop": "b:2",
            "departure": dep, "arrival": arr, "trip": "f:T1",
            "route": "f:R1", "headsign": headsign, "source": "f",
            "estimated": False,
        }],
        "estimated_ground_meters": 0,
        "coverage": [],
        "status": "Scheduled feasibility only.",
    }


def _round_trip(dep, arr, ret_dep, ret_arr, latest_dep, latest_arr):
    plan = _journey(dep, arr)
    plan["return"] = _journey(ret_dep, ret_arr, "Springfield")
    plan["latest_return"] = _journey(latest_dep, latest_arr, "Springfield")
    return plan


class FakeTransport:
    """Canned Atlas responses keyed by path and plan endpoints."""

    def __init__(self):
        self.calls = []
        self.coverage_rows = _coverage_rows()
        self.plans = {}
        self.coverage_error = None
        self.plan_error = None

    def __call__(self, url, timeout):
        self.calls.append(url)
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path.endswith("/coverage"):
            if self.coverage_error is not None:
                raise self.coverage_error
            return 200, json.dumps(self.coverage_rows).encode()
        if parsed.path.endswith("/plan"):
            if self.plan_error is not None:
                raise self.plan_error
            key = (params["from"][0], params["to"][0])
            status, payload = self.plans.get(key, (200, {
                "found": False,
                "message": "No itinerary found in the loaded feeds and "
                           "selected time window.",
                "coverage": self.coverage_rows,
            }))
            return status, json.dumps(payload).encode()
        return 404, json.dumps({"error": "Unknown API endpoint"}).encode()


def _client(transport):
    return AtlasClient("http://atlas.invalid", transport=transport)


def _feasible_transport():
    transport = FakeTransport()
    # come_to_me: friend pvta:5101 -> home hartford:6, out 08:00-09:00,
    # earliest return 11:00-12:00, latest return 20:00-21:00.
    transport.plans[("pvta:5101", "hartford:6")] = (
        200, _round_trip(28800, 32400, 39600, 43200, 72000, 75600))
    # go_to_them: home -> friend, out 08:30-09:30, returns 12:00/19:00.
    transport.plans[("hartford:6", "pvta:5101")] = (
        200, _round_trip(30600, 34200, 43200, 46800, 68400, 72000))
    return transport


class AssessVisitTests(unittest.TestCase):
    def test_feasible_round_trip_both_modes(self):
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(_feasible_transport()))
        come = result["modes"]["come_to_me"]
        self.assertEqual(come["verdict"], btm.FEASIBLE)
        self.assertEqual(come["outbound"]["arrival"], 32400)
        self.assertEqual(come["return"]["departure"], 39600)
        self.assertEqual(come["latest_return"]["departure"], 72000)
        # Together: latest return departure (20:00) minus arrival (09:00).
        self.assertEqual(come["time_together_seconds"], 39600)
        # Margin beyond the requested two-hour visit.
        self.assertEqual(come["margin_seconds"], 39600 - 7200)
        go = result["modes"]["go_to_them"]
        self.assertEqual(go["verdict"], btm.FEASIBLE)
        self.assertEqual(result["coverage_gaps"], [])

    def test_outbound_only_is_not_feasible(self):
        transport = _feasible_transport()
        plan = _journey(28800, 32400)
        plan["return"] = {"found": False,
                          "message": "Visit ends after the selected "
                                     "return deadline."}
        transport.plans[("pvta:5101", "hartford:6")] = (200, plan)
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(transport))
        come = result["modes"]["come_to_me"]
        self.assertEqual(come["verdict"], btm.NOT_FEASIBLE)
        self.assertEqual(come["reason"], "no_feasible_return")
        self.assertIsNotNone(come["outbound"])
        self.assertIsNone(come["return"])

    def test_no_outbound_is_not_feasible(self):
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(FakeTransport()))
        for mode in ("come_to_me", "go_to_them"):
            self.assertEqual(result["modes"][mode]["verdict"],
                             btm.NOT_FEASIBLE)
            self.assertEqual(result["modes"][mode]["reason"],
                             "no_outbound_journey")

    def test_out_of_period_feed_is_unknown_never_not_feasible(self):
        transport = FakeTransport()
        transport.coverage_rows = _coverage_rows(pvta_in_period=False)
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(transport))
        for mode in ("come_to_me", "go_to_them"):
            verdict = result["modes"][mode]
            self.assertEqual(verdict["verdict"], btm.UNKNOWN)
            self.assertEqual(verdict["reason"],
                             "feed_out_of_service_period:pvta")
        self.assertIn("pvta", result["coverage_gaps"])

    def test_unloaded_feed_is_unknown(self):
        transport = FakeTransport()
        transport.coverage_rows = _coverage_rows(pvta_status="not_downloaded",
                                                 pvta_in_period=False)
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(transport))
        self.assertEqual(result["modes"]["come_to_me"]["verdict"], btm.UNKNOWN)
        self.assertEqual(result["modes"]["come_to_me"]["reason"],
                         "feed_not_loaded:pvta")

    def test_server_down_is_unknown_not_an_exception(self):
        transport = FakeTransport()
        transport.coverage_error = AtlasUnavailable("connection refused")
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(transport))
        for mode in ("come_to_me", "go_to_them"):
            self.assertEqual(result["modes"][mode]["verdict"], btm.UNKNOWN)
            self.assertEqual(result["modes"][mode]["reason"],
                             "atlas_unreachable")

    def test_plan_transport_failure_is_unknown(self):
        transport = _feasible_transport()
        transport.plan_error = AtlasUnavailable("timed out")
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(transport))
        self.assertEqual(result["modes"]["come_to_me"]["verdict"], btm.UNKNOWN)
        self.assertEqual(result["modes"]["come_to_me"]["reason"],
                         "atlas_unreachable")

    def test_unknown_stop_is_unknown(self):
        transport = _feasible_transport()
        transport.plans[("pvta:5101", "hartford:6")] = (
            400, {"error": "Unknown origin stop"})
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(transport))
        come = result["modes"]["come_to_me"]
        self.assertEqual(come["verdict"], btm.UNKNOWN)
        self.assertEqual(come["reason"], "unknown_stop")

    def test_non_inner_tier_refused_before_any_network(self):
        transport = FakeTransport()
        outsider = FriendRef("Casual Acquaintance", "pvta:5101",
                             tier="acquaintance")
        with self.assertRaises(NotInnerTierError):
            assess_visit(outsider, HOME, WHEN, 120, client=_client(transport))
        self.assertEqual(transport.calls, [])

    def test_invalid_timing_parameters(self):
        client = _client(FakeTransport())
        with self.assertRaises(ValueError):
            assess_visit(FRIEND, HOME, WHEN, -5, client=client)
        with self.assertRaises(ValueError):
            assess_visit(FRIEND, HOME, WHEN, 60, client=client,
                         deadline_seconds=100)


class DraftOutreachTests(unittest.TestCase):
    def _feasible_result(self):
        return assess_visit(FRIEND, HOME, WHEN, 120,
                            client=_client(_feasible_transport()))

    def test_draft_is_labelled_and_settled(self):
        draft = draft_outreach(self._feasible_result(), "come_to_me")
        self.assertEqual(draft["kind"], "draft_outreach")
        self.assertEqual(draft["status"], "draft")
        self.assertTrue(draft["requires_owner_approval"])
        self.assertEqual(draft["to"], "Fixture Friend")
        text = draft["text"]
        self.assertIn("Fixture Friend", text)
        self.assertIn("nothing for you to work out", text)
        self.assertIn("back home by 12:00", text)
        self.assertIn("stay until 20:00", text)

    def test_draft_go_to_them(self):
        draft = draft_outreach(self._feasible_result(), "go_to_them")
        self.assertEqual(draft["mode"], "go_to_them")
        self.assertIn("I'm coming to you", draft["text"])

    def test_draft_refuses_non_feasible_mode(self):
        result = assess_visit(FRIEND, HOME, WHEN, 120,
                              client=_client(FakeTransport()))
        with self.assertRaises(ValueError):
            draft_outreach(result, "come_to_me")
        with self.assertRaises(ValueError):
            draft_outreach(result, "sideways")

    def test_module_has_no_send_path(self):
        public = [name for name in dir(btm) if not name.startswith("_")]
        offenders = [
            name for name in public
            if any(key in name.lower()
                   for key in ("send", "transmit", "smtp", "post_to"))
        ]
        self.assertEqual(offenders, [])
        source = Path(btm.__file__).read_text(encoding="utf-8")
        self.assertNotIn("smtplib", source)
        self.assertNotIn("sendmail", source)


ATLAS_URL = os.environ.get("PERCIVAL_ATLAS_URL", "http://127.0.0.1:8000")


def _atlas_reachable() -> bool:
    try:
        url = ATLAS_URL + "/api/v1/coverage?date=2026-11-17"
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


@unittest.skipUnless(_atlas_reachable(),
                     "Transit Atlas server not reachable; live test skipped")
class LiveAtlasTests(unittest.TestCase):
    """One live pass against the real Atlas and its loaded GTFS data.

    Fixture stops verified against the Atlas database: ``pvta:5101``
    is Springfield's "Union Station Bay 1" and ``hartford:6`` is
    Hartford Union Station. The service date is chosen from the
    Atlas's own coverage rows (first weekday with both the pvta and
    hartford feeds imported and in their service periods).
    """

    def test_live_come_to_me_feasible(self):
        client = AtlasClient(ATLAS_URL, timeout=180.0)
        today = datetime.now(btm.ATLAS_TIMEZONE).date()
        chosen = None
        for offset in range(45):
            day = today + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            rows = {row["feed"]: row for row in client.coverage(day.isoformat())}
            if all(
                rows.get(feed, {}).get("status") == "imported"
                and rows.get(feed, {}).get("in_service_period")
                for feed in ("pvta", "hartford")
            ):
                chosen = day
                break
        if chosen is None:
            self.skipTest("No in-period weekday for pvta+hartford feeds "
                          "in the loaded Atlas data")
        when = datetime(chosen.year, chosen.month, chosen.day, 8, 0)
        result = assess_visit(FRIEND, HOME, when, 120, client=client)
        come = result["modes"]["come_to_me"]
        self.assertEqual(come["verdict"], btm.FEASIBLE,
                         f"come_to_me on {chosen}: {come['reason']} "
                         f"{come['detail']}")
        self.assertGreaterEqual(come["margin_seconds"], 0)
        go = result["modes"]["go_to_them"]
        self.assertNotEqual(go["verdict"], btm.UNKNOWN,
                            f"go_to_them on {chosen}: {go['reason']}")
        draft = draft_outreach(result, "come_to_me")
        self.assertEqual(draft["status"], "draft")
        self.assertIn("Fixture Friend", draft["text"])


if __name__ == "__main__":
    unittest.main()
