"""Dropping events that give a year away, and tidying the rest."""

from __future__ import annotations

import pytest

from fakes import event
from puzzle_generator.cleaning import EventCleaner

cleaner = EventCleaner()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Lord Nelson (pictured) wins at Trafalgar.", "Lord Nelson wins at Trafalgar."),
        ("The ship (pictured), a frigate, sinks.", "The ship, a frigate, sinks."),
        ("Two leaders (pictured, left) meet.", "Two leaders meet."),
        ("The bridge (Pictured) opens.", "The bridge opens."),
        ("A statue (depicted) is unveiled.", "A statue is unveiled."),
    ],
)
def test_strips_references_to_the_main_page_image(text: str, expected: str) -> None:
    cleaned = cleaner.clean_event(event(1805, text=text))

    assert cleaned is not None
    assert cleaned.text == expected
    assert cleaned.adapted


def test_leaves_clean_text_untouched_and_not_adapted() -> None:
    original = event(1805, text="Nelson wins at Trafalgar.")

    assert cleaner.clean_event(original) is original


@pytest.mark.parametrize(
    "text",
    [
        "War of 1812: American forces lose a battle.",
        "The 1960s counterculture reaches its peak.",
        "Caesar's reforms, begun in 46 BC, take effect.",
        "Construction started in 474 BCE is finished.",
        "Vesuvius, which erupted in AD 79, stirs again.",
        "Vesuvius, which erupted in 79 AD, stirs again.",
    ],
)
def test_drops_events_whose_text_names_a_year(text: str) -> None:
    assert cleaner.clean_event(event(1900, text=text)) is None


def test_drops_events_whose_text_names_their_own_early_year() -> None:
    assert cleaner.clean_event(event(476, text="In 476, Odoacer deposes the emperor.")) is None


@pytest.mark.parametrize(
    "text",
    [
        "A Boeing 747 makes its first flight.",
        "About 1,500 people are killed.",
        "The 3000 troops withdraw.",
    ],
)
def test_keeps_numbers_that_are_not_years(text: str) -> None:
    assert cleaner.clean_event(event(1969, text=text)) is not None


def test_drops_events_that_were_only_an_image_reference() -> None:
    assert cleaner.clean_event(event(1900, text="(pictured)")) is None


def test_clean_keeps_order_and_drops_the_unusable() -> None:
    events = [
        event(1805, text="Nelson wins at Trafalgar."),
        event(1812, text="War of 1812: a battle."),
        event(1969, text="Apollo 12 (pictured) launches."),
    ]

    cleaned = cleaner.clean(events)

    assert [e.year for e in cleaned] == [1805, 1969]
    assert cleaned[1].text == "Apollo 12 launches."
