"""F-001 feasibility core: "come to me" / "go to them" visit assessment.

This module is the first built slice of feature F-001 in
``FEATURE_QUEUE_muse.md`` (the "bring to me" button). It answers the
round-trip feasibility question at the heart of the button and produces
a draft outreach text. It deliberately does **not** implement the
persistent friend registry, the workflow engine, or any UI surface —
those remain Codex-class work scoped in ``CODEX_HANDOFF.md``.

Design rules (from the F-001 spec and the Percival contract):

- **Inner tier only.** The button exists for people close enough that
  "come to me" needs no explanation attached. :func:`assess_visit`
  refuses a :class:`FriendRef` whose tier is not the inner tier, in
  code, before any network call is made.
- **The guest carries no logistics.** The design test for F-001: if
  the friend still has to think about transport, the workflow failed.
  A feasible assessment therefore always includes the journey *home*,
  and :func:`draft_outreach` speaks in settled plans ("here's how
  you'll get here, here's how you'll get home"), never in problems.
- **Three-state verdicts.** Each mode is ``feasible``,
  ``not_feasible``, or ``unknown``. Missing data — a feed not loaded,
  a date outside a feed's service period, an Atlas that cannot be
  reached — yields ``unknown``, never ``not_feasible``. This mirrors
  the Transit Atlas's own Mobility Bubble discipline: a stop is
  unevaluable when its own feed is unevaluable.
- **Drafts only; no send path.** :func:`draft_outreach` returns a
  string in a structure labelled ``draft`` with
  ``requires_owner_approval`` set. There is intentionally no function
  in this module that can send, transmit, or post anything; messaging
  a friend requires Branden's explicit approval at send time, outside
  this module (AGENTS.md, ADR-003).
- **Scheduled evidence, stated as such.** Verdicts rest on the Transit
  Atlas ``/api/v1`` contract (published GTFS; see the Atlas ``API.md``
  and ``server.py``). Scheduled feasibility is not live service, and
  ground legs are the router's estimates. The plan object carries the
  Atlas coverage rows as evidence so a human can see the basis.

Atlas contract facts relied on (verified against ``server.py``):

- ``GET /api/v1/plan`` with ``return=1`` and ``visit=<seconds>`` returns
  the earliest outbound itinerary plus ``return`` (earliest return
  itinerary starting at outbound arrival + visit) and ``latest_return``
  (latest feasible return) within the same ``deadline``. This — not
  the ``bubble`` endpoint, which answers set membership inside a
  budget of at most 14400 seconds rather than producing itineraries —
  is the primitive this slice composes return feasibility from.
- A plan result is ``{"found": true, "departure", "arrival", "legs",
  ...}`` or ``{"found": false, "message", "coverage"}``; the Atlas
  itself states that ``found: false`` means no result under loaded
  data, not that no transit exists.
- ``GET /api/v1/coverage?date=`` returns one row per feed:
  ``{"feed", "status", "in_service_period", "start", "end"}``.
- Unknown stops and invalid input produce HTTP 400 with
  ``{"error": "..."}``; unexpected failures produce HTTP 500.
- Times are integer service-day seconds in America/New_York; values
  above 86400 fall on the following calendar day, and ``deadline``
  may range up to 172799.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Optional
from zoneinfo import ZoneInfo

ATLAS_TIMEZONE = ZoneInfo("America/New_York")

#: The only relationship tier F-001 serves (F-001 elaboration,
#: 2026-11-14): close friends and partners, enabled in advance.
INNER_TIER = "inner"

DEFAULT_ATLAS_URL = "http://127.0.0.1:8000"

#: The Atlas connection scan over the full loaded network is not fast
#: (tens of seconds observed against all six feeds), so the default
#: timeout is generous — but bounded, per the foundation's discipline.
DEFAULT_TIMEOUT_SECONDS = 120.0

END_OF_SERVICE_DAY = 86399
MAX_DEADLINE = 172799

FEASIBLE = "feasible"
NOT_FEASIBLE = "not_feasible"
UNKNOWN = "unknown"

MODE_COME_TO_ME = "come_to_me"
MODE_GO_TO_THEM = "go_to_them"


class AtlasError(Exception):
    """Base class for Transit Atlas client failures."""


class AtlasUnavailable(AtlasError):
    """The Atlas could not be reached or returned an unusable reply.

    This is a data-availability failure: assessments degrade to the
    ``unknown`` verdict rather than guessing at feasibility.
    """


class AtlasRequestError(AtlasError):
    """The Atlas rejected the request (HTTP 4xx) with a stated error."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Atlas HTTP {status}: {message}")
        self.status = status
        self.message = message


class NotInnerTierError(ValueError):
    """F-001 was asked to assess a friend outside the inner tier."""


@dataclass(frozen=True)
class FriendRef:
    """An in-memory reference to a supported friend (F-001).

    Fixture-friendly by design: the persistent friend registry is
    Codex-class work. ``tier`` defaults to the inner tier; any other
    value makes :func:`assess_visit` refuse the record.
    """

    name: str
    home_stop_id: str
    tier: str = INNER_TIER


@dataclass(frozen=True)
class HomeRef:
    """Branden's home base, as an Atlas stop reference."""

    home_stop_id: str
    label: str = "home"


#: A transport takes (url, timeout_seconds) and returns
#: (http_status, body_bytes). It raises :class:`AtlasUnavailable` for
#: transport-level failures. Injectable so tests never touch a network.
Transport = Callable[[str, float], "tuple[int, bytes]"]


def _urllib_transport(url: str, timeout: float) -> "tuple[int, bytes]":
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AtlasUnavailable(f"Transit Atlas unreachable: {exc}") from exc


class AtlasClient:
    """Minimal read-only client for the Transit Atlas ``/api/v1``.

    Standard library only, consistent with the foundation seed. Every
    failure mode is an :class:`AtlasError` subclass; this client never
    fabricates a result.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_ATLAS_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Optional[Transport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport or _urllib_transport

    def _get_json(self, path: str, params: Mapping[str, Any]) -> Any:
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}?{query}"
        status, body = self._transport(url, self.timeout)
        if status >= 500:
            raise AtlasUnavailable(f"Transit Atlas returned HTTP {status}")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AtlasUnavailable("Transit Atlas returned malformed JSON") from exc
        if status != 200:
            message = ""
            if isinstance(payload, Mapping):
                message = str(payload.get("error", ""))
            raise AtlasRequestError(status, message or f"HTTP {status}")
        return payload

    def coverage(self, date_iso: str) -> "list[Mapping[str, Any]]":
        """Per-feed coverage rows for a service date (Atlas contract)."""
        payload = self._get_json("/api/v1/coverage", {"date": date_iso})
        if not isinstance(payload, list):
            raise AtlasUnavailable("Unexpected coverage payload from Atlas")
        return payload

    def plan(
        self,
        from_stop: str,
        to_stop: str,
        date_iso: str,
        start_seconds: int,
        deadline_seconds: int,
        visit_seconds: int,
        ground_mode: str = "walk",
    ) -> "dict[str, Any]":
        """Earliest itinerary plus earliest/latest returns (``return=1``)."""
        payload = self._get_json(
            "/api/v1/plan",
            {
                "from": from_stop,
                "to": to_stop,
                "date": date_iso,
                "time": start_seconds,
                "deadline": deadline_seconds,
                "return": 1,
                "visit": visit_seconds,
                "mode": ground_mode,
            },
        )
        if not isinstance(payload, dict):
            raise AtlasUnavailable("Unexpected plan payload from Atlas")
        return payload


def _feed_of(stop_id: str) -> str:
    return stop_id.split(":", 1)[0]


def _feed_evaluable(
    coverage: "list[Mapping[str, Any]]", feed: str
) -> "tuple[bool, Optional[str]]":
    """Whether a feed can be evaluated at all on the requested date."""
    for row in coverage:
        if row.get("feed") == feed:
            if row.get("status") != "imported":
                return False, f"feed_not_loaded:{feed}"
            if not row.get("in_service_period", False):
                return False, f"feed_out_of_service_period:{feed}"
            return True, None
    return False, f"feed_absent_from_coverage:{feed}"


def _coverage_gaps(coverage: "list[Mapping[str, Any]]") -> "list[str]":
    return [
        str(row.get("feed"))
        for row in coverage
        if row.get("status") != "imported" or not row.get("in_service_period", False)
    ]


def _format_time(seconds: int) -> str:
    seconds = int(seconds)
    suffix = ""
    if seconds >= 86400:
        suffix = " (after midnight)"
        seconds -= 86400
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}{suffix}"


def _summarize_journey(plan: Mapping[str, Any]) -> "dict[str, Any]":
    legs = []
    for leg in plan.get("legs", []):
        legs.append(
            {
                "kind": leg.get("kind"),
                "route": leg.get("route"),
                "headsign": leg.get("headsign"),
                "from_stop": leg.get("from_stop"),
                "to_stop": leg.get("to_stop"),
                "departure": leg.get("departure"),
                "arrival": leg.get("arrival"),
                "estimated": bool(leg.get("estimated")),
            }
        )
    departure = int(plan["departure"])
    arrival = int(plan["arrival"])
    return {
        "departure": departure,
        "arrival": arrival,
        "departure_time": _format_time(departure),
        "arrival_time": _format_time(arrival),
        "duration_seconds": arrival - departure,
        "legs": legs,
        "estimated_ground_meters": plan.get("estimated_ground_meters"),
    }


def _mode_shell(mode: str, origin: str, destination: str) -> "dict[str, Any]":
    return {
        "mode": mode,
        "from_stop": origin,
        "to_stop": destination,
        "verdict": UNKNOWN,
        "reason": None,
        "detail": None,
        "outbound": None,
        "return": None,
        "latest_return": None,
        "time_together_seconds": None,
        "margin_seconds": None,
    }


def _assess_mode(
    client: AtlasClient,
    mode: str,
    origin: str,
    destination: str,
    date_iso: str,
    start_seconds: int,
    deadline_seconds: int,
    visit_seconds: int,
    ground_mode: str,
    coverage: "list[Mapping[str, Any]]",
) -> "dict[str, Any]":
    result = _mode_shell(mode, origin, destination)
    for stop in (origin, destination):
        evaluable, reason = _feed_evaluable(coverage, _feed_of(stop))
        if not evaluable:
            result["reason"] = reason
            result["detail"] = (
                f"Stop {stop} is served by a feed that cannot be evaluated "
                "on this date; missing data is not evidence of no service."
            )
            return result
    try:
        plan = client.plan(
            origin,
            destination,
            date_iso,
            start_seconds,
            deadline_seconds,
            visit_seconds,
            ground_mode,
        )
    except AtlasUnavailable as exc:
        result["reason"] = "atlas_unreachable"
        result["detail"] = str(exc)
        return result
    except AtlasRequestError as exc:
        if "unknown" in exc.message.lower() and "stop" in exc.message.lower():
            result["reason"] = "unknown_stop"
        else:
            result["reason"] = "atlas_request_error"
        result["detail"] = exc.message
        return result
    if not plan.get("found"):
        result["verdict"] = NOT_FEASIBLE
        result["reason"] = "no_outbound_journey"
        result["detail"] = plan.get("message")
        return result
    outbound = _summarize_journey(plan)
    result["outbound"] = outbound
    earliest_return = plan.get("return") or {}
    if not earliest_return.get("found"):
        result["verdict"] = NOT_FEASIBLE
        result["reason"] = "no_feasible_return"
        result["detail"] = earliest_return.get("message") or (
            "The outbound journey exists, but no return itinerary was "
            "found inside the deadline after the requested visit."
        )
        return result
    result["return"] = _summarize_journey(earliest_return)
    latest_return = plan.get("latest_return") or {}
    anchor = result["return"]
    if latest_return.get("found"):
        result["latest_return"] = _summarize_journey(latest_return)
        anchor = result["latest_return"]
    together = int(anchor["departure"]) - int(outbound["arrival"])
    result["verdict"] = FEASIBLE
    result["reason"] = "round_trip_found"
    result["time_together_seconds"] = together
    result["margin_seconds"] = together - visit_seconds
    return result


def assess_visit(
    friend: FriendRef,
    home: HomeRef,
    when: datetime,
    visit_minutes: int,
    *,
    client: Optional[AtlasClient] = None,
    deadline_seconds: int = END_OF_SERVICE_DAY,
    ground_mode: str = "walk",
) -> "dict[str, Any]":
    """Assess both F-001 modes for one proposed visit.

    ``when`` is the earliest departure time for the travelling party,
    interpreted in America/New_York (the Atlas's service-day frame);
    ``visit_minutes`` is the time together the plan must protect.
    ``deadline_seconds`` bounds the return (service-day seconds, at
    most 172799; default: end of the service day).

    Returns the plan object described in the module docstring. Raises
    :class:`NotInnerTierError` for a friend outside the inner tier and
    :class:`ValueError` for impossible timing parameters. Atlas
    failures never raise out of this function; they degrade the
    affected verdicts to ``unknown`` with a stated reason.
    """
    if friend.tier != INNER_TIER:
        raise NotInnerTierError(
            f"F-001 serves the inner tier only; {friend.name!r} is "
            f"recorded as tier {friend.tier!r}."
        )
    if visit_minutes < 0:
        raise ValueError("visit_minutes must not be negative")
    if not 0 <= deadline_seconds <= MAX_DEADLINE:
        raise ValueError(f"deadline_seconds must lie within 0..{MAX_DEADLINE}")
    local = when.astimezone(ATLAS_TIMEZONE) if when.tzinfo else when
    date_iso = local.date().isoformat()
    start_seconds = local.hour * 3600 + local.minute * 60 + local.second
    if deadline_seconds < start_seconds:
        raise ValueError("deadline_seconds precedes the requested start time")
    visit_seconds = int(visit_minutes * 60)
    client = client or AtlasClient()

    plan_object: "dict[str, Any]" = {
        "kind": "f001_visit_assessment",
        "version": 1,
        "friend": {
            "name": friend.name,
            "home_stop_id": friend.home_stop_id,
            "tier": friend.tier,
        },
        "home": {"home_stop_id": home.home_stop_id, "label": home.label},
        "date": date_iso,
        "start_seconds": start_seconds,
        "start_time": _format_time(start_seconds),
        "visit_minutes": visit_minutes,
        "deadline_seconds": deadline_seconds,
        "ground_mode": ground_mode,
        "modes": {},
        "coverage": None,
        "coverage_gaps": [],
        "evidence": (
            "Scheduled feasibility from the Transit Atlas /api/v1 "
            "(published GTFS). Not live service; ground legs are "
            "estimates, and a verdict is only as complete as the "
            "coverage rows attached here."
        ),
    }
    try:
        coverage = client.coverage(date_iso)
    except AtlasError as exc:
        for mode, origin, destination in (
            (MODE_COME_TO_ME, friend.home_stop_id, home.home_stop_id),
            (MODE_GO_TO_THEM, home.home_stop_id, friend.home_stop_id),
        ):
            shell = _mode_shell(mode, origin, destination)
            shell["reason"] = "atlas_unreachable"
            shell["detail"] = str(exc)
            plan_object["modes"][mode] = shell
        return plan_object
    plan_object["coverage"] = coverage
    plan_object["coverage_gaps"] = _coverage_gaps(coverage)
    plan_object["modes"][MODE_COME_TO_ME] = _assess_mode(
        client,
        MODE_COME_TO_ME,
        friend.home_stop_id,
        home.home_stop_id,
        date_iso,
        start_seconds,
        deadline_seconds,
        visit_seconds,
        ground_mode,
        coverage,
    )
    plan_object["modes"][MODE_GO_TO_THEM] = _assess_mode(
        client,
        MODE_GO_TO_THEM,
        home.home_stop_id,
        friend.home_stop_id,
        date_iso,
        start_seconds,
        deadline_seconds,
        visit_seconds,
        ground_mode,
        coverage,
    )
    return plan_object


def _describe_journey(summary: Mapping[str, Any]) -> str:
    parts = []
    for leg in summary.get("legs", []):
        if leg.get("kind") == "transit":
            if leg.get("headsign"):
                parts.append(
                    f"the {_format_time(int(leg['departure']))} departure "
                    f"towards {leg['headsign']}"
                )
            else:
                parts.append(f"the {_format_time(int(leg['departure']))} departure")
        else:
            parts.append("a short walk")
    return ", then ".join(parts) if parts else "a direct trip"


def draft_outreach(plan_object: Mapping[str, Any], mode: str) -> "dict[str, Any]":
    """Draft the guest-facing message for one feasible mode.

    The text is a settled plan, not a problem: how they get here, how
    they get home, nothing left for the guest to work out (the F-001
    design test). The result is labelled ``draft`` and carries
    ``requires_owner_approval``; this module contains no way to send
    it. Raises :class:`ValueError` unless the chosen mode's verdict is
    ``feasible``.
    """
    if mode not in (MODE_COME_TO_ME, MODE_GO_TO_THEM):
        raise ValueError(f"Unknown F-001 mode: {mode!r}")
    assessment = plan_object["modes"][mode]
    if assessment["verdict"] != FEASIBLE:
        raise ValueError(
            f"Cannot draft outreach for mode {mode!r}: verdict is "
            f"{assessment['verdict']!r}, not 'feasible'."
        )
    name = plan_object["friend"]["name"]
    date = plan_object["date"]
    outbound = assessment["outbound"]
    way_back = assessment["return"]
    latest = assessment.get("latest_return")
    if mode == MODE_COME_TO_ME:
        text = (
            f"Hi {name} — come to mine on {date}? I've sorted the whole "
            f"trip, so there's nothing for you to work out. Getting here: "
            f"{_describe_journey(outbound)} — you'll be with me by "
            f"{outbound['arrival_time']}. Getting home: "
            f"{_describe_journey(way_back)} — back home by "
            f"{way_back['arrival_time']}."
        )
        if latest:
            text += (
                f" And if we lose track of time, you can stay until "
                f"{latest['departure_time']} and still get home."
            )
        text += " Just bring yourself."
    else:
        text = (
            f"Hi {name} — I'm coming to you on {date}, all sorted at my "
            f"end. I'll be with you by {outbound['arrival_time']} "
            f"({_describe_journey(outbound)}). I'll head back at "
            f"{way_back['departure_time']} and be home by "
            f"{way_back['arrival_time']}, so there's nothing for you to "
            f"plan around. Just be there."
        )
    return {
        "kind": "draft_outreach",
        "status": "draft",
        "requires_owner_approval": True,
        "mode": mode,
        "to": name,
        "text": text,
    }
