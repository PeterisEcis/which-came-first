"""Storing generated puzzles: start order, public ids, and replacing."""

from __future__ import annotations

import random
from datetime import date
from uuid import uuid4

import pytest

from fakes import ANSWER_YEARS, SOURCE_URL, generated_puzzle
from game.importer import PuzzleExists, PuzzleImporter, PuzzleInUse
from game.models import Play, Puzzle

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 13)


def save(*, replace: bool = False, seed: int = 1) -> Puzzle:
    return PuzzleImporter(random.Random(seed)).save(generated_puzzle(DAY), replace=replace)


def test_stores_the_puzzle_and_its_events() -> None:
    puzzle = save()

    assert (puzzle.date, puzzle.feed, puzzle.source_url) == (DAY, "selected", SOURCE_URL)
    events = list(puzzle.events.order_by("year"))
    assert [event.year for event in events] == list(ANSWER_YEARS)
    assert events[0].articles == [
        {"title": "Article 1066", "url": "https://en.wikipedia.org/wiki/Article_1066"}
    ]


def test_event_keys_are_distinct_and_letters_only() -> None:
    keys = save().answer_keys()

    assert len(set(keys)) == 5
    assert all(key.isascii() and key.isalpha() for key in keys)


def test_the_start_order_is_never_already_sorted() -> None:
    importer = PuzzleImporter(random.Random(0))

    starts = [importer.start_positions(5) for _ in range(500)]

    assert [0, 1, 2, 3, 4] not in starts
    assert importer.start_positions(2) == [1, 0]


def test_stored_events_come_out_in_their_start_order() -> None:
    puzzle = save()

    starting_years = [event.year for event in puzzle.events.all()]

    assert starting_years != sorted(starting_years)
    assert [event.start_position for event in puzzle.events.all()] == [0, 1, 2, 3, 4]


def test_refuses_a_date_that_already_has_a_puzzle() -> None:
    save()

    with pytest.raises(PuzzleExists):
        save()


def test_replaces_a_puzzle_nobody_has_played() -> None:
    old_keys = save().answer_keys()

    new_keys = save(replace=True, seed=2).answer_keys()

    assert Puzzle.objects.count() == 1
    assert new_keys != old_keys


def test_wont_replace_a_puzzle_someone_has_played() -> None:
    puzzle = save()
    Play.objects.create(puzzle=puzzle, player_id=uuid4())

    with pytest.raises(PuzzleInUse):
        save(replace=True)
