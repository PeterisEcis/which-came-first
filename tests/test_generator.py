"""The whole generator, from a feed response to a puzzle."""

from __future__ import annotations

from datetime import date

import pytest

from fakes import FakeHttp, feed_entry, feed_payload
from puzzle_generator.config import GeneratorSettings
from puzzle_generator.generator import PuzzleGenerator
from puzzle_generator.models import Puzzle
from puzzle_generator.selection import NotEnoughEvents

DAY = date(2026, 10, 13)
SETTINGS = GeneratorSettings(contact="tests")

FEED = feed_payload(
    feed_entry(-474, "Hiero I defeats the Etruscans off Cumae.", "Battle of Cumae"),
    feed_entry(54, "Nero becomes Roman emperor.", "Nero"),
    feed_entry(1307, "Knights Templar (pictured) are arrested across France.", "Knights Templar"),
    feed_entry(1792, "The cornerstone of the White House is laid.", "White House"),
    feed_entry(1812, "War of 1812: Americans lose at Queenston Heights.", "War of 1812"),
    feed_entry(1884, "Greenwich is adopted as the prime meridian.", "Prime meridian"),
    feed_entry(1923, "Ankara becomes the capital of Turkey.", "Ankara"),
    feed_entry(1943, "Italy declares war on Germany.", "Italy"),
    feed_entry(1972, "A plane carrying a rugby team crashes in the Andes.", "Andes"),
)


def generate(payload: dict[str, object] = FEED, day: date = DAY) -> Puzzle:
    return PuzzleGenerator.from_settings(SETTINGS, FakeHttp(payload)).generate(day)


def test_builds_a_puzzle_of_five_events_in_chronological_order() -> None:
    puzzle = generate()

    years = [event.year for event in puzzle.events]
    assert len(years) == 5
    assert years == sorted(years)
    assert puzzle.puzzle_date == DAY
    assert puzzle.feed == "selected"


def test_events_that_name_a_year_never_make_it_in() -> None:
    puzzle = generate()

    assert 1812 not in [event.year for event in puzzle.events]


def test_same_date_gives_the_same_puzzle() -> None:
    assert generate() == generate()


def test_attribution_links_the_source_page() -> None:
    puzzle = generate()

    assert puzzle.attribution.source_url == (
        "https://en.wikipedia.org/wiki/Wikipedia:Selected_anniversaries/October_13"
    )
    assert puzzle.attribution.license_name == "CC BY-SA 4.0"


def test_attribution_says_adapted_only_when_an_event_was_edited() -> None:
    puzzle = generate()

    edited = any(event.adapted for event in puzzle.events)
    assert puzzle.attribution.adapted == edited
    assert puzzle.attribution.text.startswith("Adapted from" if edited else "From")


def test_a_day_without_enough_usable_events_fails() -> None:
    thin = feed_payload(
        feed_entry(1307, "Knights Templar are arrested.", "Knights Templar"),
        feed_entry(1812, "War of 1812: a battle.", "War of 1812"),
    )

    with pytest.raises(NotEnoughEvents):
        generate(thin)
