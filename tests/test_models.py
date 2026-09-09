"""Departure arithmetic and field mapping in custom_components/mvg/models.py.

Every test runs with the process timezone pinned to UTC, so a result never
depends on where the suite happens to run. The DST test is the deliberate
exception: it pins its own zone, because a clock change is the thing it
measures.
"""

import contextlib
import operator
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from time import tzset

import pytest

from custom_components.mvg import models

# 2026-01-01T12:00:00Z. Any instant clear of a DST transition would do.
NOW = 1767268800


@contextlib.contextmanager
def _timezone(name: str):
    """Run the block with the process timezone set to ``name``."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    tzset()
    try:
        yield
    finally:
        if previous is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = previous
        tzset()


def _freeze(monkeypatch, at: int) -> None:
    """Pin the clock ``models.py`` reads to the instant ``at``.

    This is the single place coupled to how models.py reads the clock: if it
    ever stops going through ``time.time()``, this function has to follow it.
    Only the module's own reference is replaced, so the real ``time`` module is
    untouched for everything else.
    """
    monkeypatch.setattr(models, "time", SimpleNamespace(time=lambda: float(at)))


@pytest.fixture(autouse=True)
def _utc():
    with _timezone("UTC"):
        yield


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    _freeze(monkeypatch, NOW)


def _at(offset_seconds: int) -> int:
    """The unix timestamp ``offset_seconds`` away from the frozen now."""
    return NOW + offset_seconds


def _departure(*, time: int, planned: int | None = None):
    """A departure whose two timestamps are the only thing worth looking at.

    Keyword-only on purpose: the realtime and timetable stamps are the same
    type, and swapping them is the defect this file exists to catch. ``planned``
    defaults to ``time``, i.e. a punctual departure.
    """
    return models.MvgDepartureInfo(
        time=time,
        planned=time if planned is None else planned,
        delay=0,
        line="U6",
        platform=2,
        realtime=True,
        destination="Garching-Forschungszentrum",
        transport_type="U-Bahn",
        cancelled=False,
        messages=[],
    )


both_accessors = pytest.mark.parametrize(
    "minutes",
    [
        operator.methodcaller("minutes_until_real_departure"),
        operator.methodcaller("minutes_until_planned_departure"),
    ],
    ids=["real", "planned"],
)


@both_accessors
@pytest.mark.parametrize(
    ("seconds_away", "expected"),
    [(600, 10), (120, 2), (119, 1), (60, 1), (59, 0), (1, 0), (0, 0)],
    ids=["10min", "2min", "1min59s", "exactly1min", "59s", "1s", "now"],
)
def test_minutes_are_floored_to_the_whole_minute(minutes, seconds_away, expected):
    """Part of a minute never counts. A train 59 seconds out reads 0, not 1.

    Floor rather than round is the honest reading for a departure board: it
    never tells you that you have a minute you do not have.
    """
    assert minutes(_departure(time=_at(seconds_away))) == expected


@both_accessors
@pytest.mark.parametrize(
    "seconds_ago", [1, 59, 60, 180, 86400], ids=["1s", "59s", "1min", "3min", "1day"]
)
def test_a_departure_already_gone_reports_zero_not_a_negative(minutes, seconds_ago):
    """Sensors recompute on every state read from whatever the coordinator last
    cached, so a stale cache routinely asks about a departure that has left.
    Minutes-until is a duration and a negative one is not a valid sensor value.
    """
    assert minutes(_departure(time=_at(-seconds_ago))) == 0


def test_each_accessor_reads_its_own_timestamp():
    """``time`` is the realtime departure, ``planned`` the timetable one.

    sensor.py publishes both as separate attributes. Reading either from the
    other's field makes a late train look punctual.
    """
    late = _departure(time=_at(600), planned=_at(480))
    assert late.minutes_until_real_departure() == 10
    assert late.minutes_until_planned_departure() == 8


# The dict shape produced by mvg 1.6.0 in MvgApi.departures_async
# (.venv/lib/python3.14/site-packages/mvg/mvgapi.py:485-497). "icon" is here
# because the client sends it and models.py does not model it: an unmodelled
# key must not break the coordinator update.
RAW = {
    "time": 1767268800,
    "planned": 1767268740,
    "delay": 1,
    "platform": 2,
    "realtime": True,
    "line": "U6",
    "destination": "Garching-Forschungszentrum",
    "type": "U-Bahn",
    "icon": "mdi:subway",
    "cancelled": False,
    "messages": ["Aufzug außer Betrieb"],
}


def test_from_dict_maps_every_field_the_client_sends():
    departure = models.MvgDepartureInfo.from_dict(RAW)

    assert departure.time == 1767268800
    assert departure.planned == 1767268740
    assert departure.delay == 1
    assert departure.platform == 2
    assert departure.realtime is True
    assert departure.line == "U6"
    assert departure.destination == "Garching-Forschungszentrum"
    assert departure.transport_type == "U-Bahn"  # the one key that is renamed
    assert departure.cancelled is False
    assert departure.messages == ["Aufzug außer Betrieb"]


@pytest.mark.parametrize("missing", sorted(RAW.keys() - {"icon"}))
def test_from_dict_rejects_an_incomplete_payload(missing):
    """A client that stops sending a field must fail the update loudly rather
    than yield a half-built departure. DataUpdateCoordinator turns the error
    into an unavailable entity and retries on the next interval, which recovers
    on its own; a departure with a silently defaulted timestamp does not.
    """
    with pytest.raises(KeyError):
        models.MvgDepartureInfo.from_dict(
            {k: v for k, v in RAW.items() if k != missing}
        )


# Europe/Berlin 2026: the instants at which local clocks jump.
TRANSITIONS = {
    "spring-forward": int(datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc).timestamp()),
    "fall-back": int(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc).timestamp()),
}


@pytest.mark.parametrize("transition", TRANSITIONS.values(), ids=list(TRANSITIONS))
def test_minutes_survive_a_dst_transition(transition, monkeypatch):
    """Minutes-until is elapsed time, not the gap between two local clock faces."""
    with _timezone("Europe/Berlin"):
        _freeze(monkeypatch, transition - 1800)
        assert _departure(time=transition + 1800).minutes_until_real_departure() == 60
