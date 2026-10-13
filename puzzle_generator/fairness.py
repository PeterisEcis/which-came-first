"""Rules that decide whether events can be ordered fairly.

Every rule compares two events at a time. That keeps each one small, and lets
the selector rule out a candidate the moment it clashes with one already picked
instead of testing whole sets. Adding a rule means writing one more class with a
`conflict` method and listing it in `FairnessChecker.default`.

Conflict messages name years, so they are for people reviewing a puzzle, never
for logs: a CI log on a public repo is readable by anyone.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Protocol

from puzzle_generator.models import Event


class PairRule(Protocol):
    def conflict(self, first: Event, second: Event) -> str | None:
        """Why these two can't share a puzzle, or None if they can."""
        ...


@dataclass(frozen=True)
class MinimumYearGap:
    """Years must be at least `min_gap` apart.

    Covers duplicate years too: those are 0 apart, and `min_gap` is at least 1.
    """

    min_gap: int

    def __post_init__(self) -> None:
        if self.min_gap < 1:
            raise ValueError(f"min_gap must be at least 1, got {self.min_gap}")

    def conflict(self, first: Event, second: Event) -> str | None:
        # Across the BCE/CE line this is a year too generous -- there is no year
        # 0 -- which is far below anything `min_gap` is meant to separate.
        gap = abs(first.year - second.year)
        if gap == 0:
            return f"both in {first.year_label}"
        if gap < self.min_gap:
            return (
                f"{first.year_label} and {second.year_label} are {gap} years apart "
                f"(minimum {self.min_gap})"
            )
        return None


@dataclass(frozen=True)
class NoSharedArticles:
    """Events that link the same article are probably parts of one story.

    Two battles of one war both link the war. Ordering them is trivia about that
    war, not a fair question, and the shared link spots it without a list of
    wars to maintain. It also rejects pairs that merely share a country -- an
    acceptable loss with ~15 candidates to choose from.
    """

    def conflict(self, first: Event, second: Event) -> str | None:
        shared = {article.title for article in first.articles} & {
            article.title for article in second.articles
        }
        if shared:
            return f"both link {', '.join(sorted(shared))}"
        return None


class FairnessChecker:
    """Applies a list of pair rules to candidates and to whole puzzles."""

    def __init__(self, rules: Sequence[PairRule]) -> None:
        self.rules = tuple(rules)

    @classmethod
    def default(cls, *, min_year_gap: int) -> FairnessChecker:
        return cls([MinimumYearGap(min_year_gap), NoSharedArticles()])

    def conflict(self, first: Event, second: Event) -> str | None:
        """The first rule these two break, or None."""
        for rule in self.rules:
            reason = rule.conflict(first, second)
            if reason is not None:
                return reason
        return None

    def fits(self, candidate: Event, chosen: Iterable[Event]) -> bool:
        """True if `candidate` clashes with none of the events already chosen."""
        return all(self.conflict(candidate, event) is None for event in chosen)

    def problems(self, events: Sequence[Event]) -> list[str]:
        """Every conflict in a finished set. Empty means the set is fair.

        For checking a set someone picked by hand, like the admin panel will.
        """
        return [
            reason
            for first, second in combinations(events, 2)
            if (reason := self.conflict(first, second)) is not None
        ]
