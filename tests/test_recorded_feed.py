"""The generator against a real response: the `selected` feed for 13 October.

Recorded from the live feed on 2026-10-13. If Wikipedia changes the feed's
shape, re-record it and these tests show what the parser no longer handles.
"""

from __future__ import annotations

from datetime import date

import pytest

from fakes import FakeHttp, load_fixture
from puzzle_generator.cleaning import EventCleaner
from puzzle_generator.config import GeneratorSettings
from puzzle_generator.fairness import FairnessChecker
from puzzle_generator.feed import OnThisDayClient
from puzzle_generator.generator import PuzzleGenerator
from puzzle_generator.models import Event, Puzzle

RECORDED = "onthisday_selected_10-13.json"
DAY = date(2026, 10, 13)
SETTINGS = GeneratorSettings(contact="tests")


@pytest.fixture(scope="module")
def events() -> list[Event]:
    return OnThisDayClient(FakeHttp(load_fixture(RECORDED))).fetch(DAY)


@pytest.fixture(scope="module")
def puzzle() -> Puzzle:
    return PuzzleGenerator.from_settings(SETTINGS, FakeHttp(load_fixture(RECORDED))).generate(DAY)


def test_every_entry_parses(events: list[Event]) -> None:
    assert len(events) == 17
    assert [event.year for event in events][:3] == [2019, 2016, 2013]
    assert events[-1].year == 645
    assert all(event.articles for event in events)


def test_non_breaking_spaces_become_plain_ones(events: list[Event]) -> None:
    # The feed writes "Flight 571" and "31 million" with U+00A0 between the parts.
    assert not [event for event in events if "\xa0" in event.text]
    assert any("Flight 571 crashed" in event.text for event in events)


def test_keeps_accented_text_and_titles(events: list[Event]) -> None:
    [fatima] = [event for event in events if event.year == 1917]

    assert "Fátima, Portugal" in fatima.text
    assert "Fátima, Portugal" in [article.title for article in fatima.articles]


def test_cleaning_drops_both_war_of_1812_events(events: list[Event]) -> None:
    cleaned = EventCleaner().clean(events)

    assert len(cleaned) == 15
    assert {event.year for event in events} - {event.year for event in cleaned} == {1812, 1814}


def test_cleaning_strips_every_pictured_reference(events: list[Event]) -> None:
    cleaned = EventCleaner().clean(events)

    assert not [event for event in cleaned if "pictured" in event.text]
    assert sorted(event.year for event in cleaned if event.adapted) == [1773, 2011, 2019]


def test_puzzle_is_five_fair_events_in_order(puzzle: Puzzle) -> None:
    years = [event.year for event in puzzle.events]

    assert len(years) == 5
    assert years == sorted(years)
    assert FairnessChecker.default(min_year_gap=10).problems(puzzle.events) == []


def test_no_puzzle_text_names_a_year(puzzle: Puzzle) -> None:
    assert not [
        event.text for event in puzzle.events if EventCleaner.names_a_year(event.text, event.year)
    ]
