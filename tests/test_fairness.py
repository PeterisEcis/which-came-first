"""Which events can share a puzzle."""

from __future__ import annotations

import pytest

from fakes import event
from puzzle_generator.fairness import FairnessChecker, MinimumYearGap, NoSharedArticles


class TestMinimumYearGap:
    rule = MinimumYearGap(10)

    def test_same_year_conflicts(self) -> None:
        assert self.rule.conflict(event(1812), event(1812)) == "both in 1812"

    def test_years_closer_than_the_gap_conflict(self) -> None:
        reason = self.rule.conflict(event(1812), event(1814))

        assert reason == "1812 and 1814 are 2 years apart (minimum 10)"

    def test_years_at_least_the_gap_apart_are_fine(self) -> None:
        assert self.rule.conflict(event(1800), event(1810)) is None

    def test_measures_across_the_bce_line(self) -> None:
        reason = self.rule.conflict(event(-4), event(3))

        assert reason == "4 BCE and 3 are 7 years apart (minimum 10)"

    def test_gap_below_one_would_allow_duplicate_years(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            MinimumYearGap(0)


class TestNoSharedArticles:
    rule = NoSharedArticles()

    def test_events_linking_the_same_article_conflict(self) -> None:
        first = event(1812, "War of 1812", "Battle of Queenston Heights")
        second = event(1814, "War of 1812", "Burning of Washington")

        assert self.rule.conflict(first, second) == "both link War of 1812"

    def test_events_with_different_articles_are_fine(self) -> None:
        assert self.rule.conflict(event(1066, "Hastings"), event(1815, "Waterloo")) is None

    def test_events_without_articles_are_fine(self) -> None:
        assert self.rule.conflict(event(1066), event(1815)) is None


class TestFairnessChecker:
    checker = FairnessChecker.default(min_year_gap=10)

    def test_fits_when_no_chosen_event_clashes(self) -> None:
        chosen = [event(1066), event(1492)]

        assert self.checker.fits(event(1815), chosen)
        assert not self.checker.fits(event(1490), chosen)

    def test_anything_fits_an_empty_puzzle(self) -> None:
        assert self.checker.fits(event(1066), [])

    def test_problems_lists_every_conflict_in_a_set(self) -> None:
        events = [event(1812, "War of 1812"), event(1814, "War of 1812"), event(1900)]

        assert self.checker.problems(events) == ["1812 and 1814 are 2 years apart (minimum 10)"]

    def test_a_fair_set_has_no_problems(self) -> None:
        assert self.checker.problems([event(1066), event(1492), event(1815)]) == []
