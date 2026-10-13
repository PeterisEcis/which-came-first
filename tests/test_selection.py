"""Choosing the day's events."""

from __future__ import annotations

import pytest

from fakes import event
from puzzle_generator.fairness import FairnessChecker
from puzzle_generator.selection import EventSelector, NotEnoughEvents

checker = FairnessChecker.default(min_year_gap=10)
selector = EventSelector(checker, count=5)

CANDIDATES = [event(1000 + 37 * i) for i in range(15)]


def test_same_seed_gives_the_same_events() -> None:
    first = selector.select(CANDIDATES, seed="2026-10-13")
    second = selector.select(list(CANDIDATES), seed="2026-10-13")

    assert first == second


def test_different_seeds_give_different_events() -> None:
    picks = {
        frozenset(e.year for e in selector.select(CANDIDATES, seed=f"2026-10-{day:02d}"))
        for day in range(1, 11)
    }

    assert len(picks) > 1


def test_picks_count_events_that_pass_the_rules_together() -> None:
    chosen = selector.select(CANDIDATES, seed="2026-10-13")

    assert len(chosen) == 5
    assert checker.problems(chosen) == []


def test_backtracks_out_of_a_dead_end() -> None:
    # 1050 is too close to both 1000 and 1100, so the only fair three are the
    # other three. Picking 1050 first leaves no way to finish; the search has to
    # undo it rather than give up.
    candidates = [event(1050), event(1000), event(1100), event(1300)]
    picky = EventSelector(FairnessChecker.default(min_year_gap=60), count=3)

    for day in range(1, 21):
        chosen = picky.select(candidates, seed=f"2026-10-{day:02d}")
        assert sorted(e.year for e in chosen) == [1000, 1100, 1300]


def test_too_few_candidates() -> None:
    with pytest.raises(NotEnoughEvents, match="only 4 usable events"):
        selector.select(CANDIDATES[:4], seed="2026-10-13")


def test_no_fair_set_among_the_candidates() -> None:
    crowded = [event(1900 + i) for i in range(8)]

    with pytest.raises(NotEnoughEvents, match="fairness rules"):
        selector.select(crowded, seed="2026-10-13")


def test_a_puzzle_needs_at_least_two_events() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        EventSelector(checker, count=1)
