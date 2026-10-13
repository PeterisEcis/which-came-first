"""Picking the day's events: random-looking, but the same every time for a date.

The candidates are shuffled by a random generator seeded with the date, then
searched in that order for the first set the fairness rules accept. The same
date and the same candidates always give the same puzzle.

The search backtracks, so it finds a fair set whenever one exists, even where
picking greedily would paint itself into a corner. Choosing 5 of ~20 is at most
15,504 sets, so there is no need for anything cleverer.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from puzzle_generator.fairness import FairnessChecker
from puzzle_generator.models import Event


class NotEnoughEvents(RuntimeError):
    """No fair set of the requested size exists among the candidates."""


class EventSelector:
    """Chooses `count` events that the fairness rules accept together."""

    def __init__(self, checker: FairnessChecker, *, count: int = 5) -> None:
        if count < 2:
            raise ValueError(f"a puzzle needs at least 2 events to order, got {count}")
        self.checker = checker
        self.count = count

    def select(self, candidates: Sequence[Event], seed: str) -> list[Event]:
        """`count` events from `candidates`, chosen the same way for the same seed.

        Raises:
            NotEnoughEvents: too few candidates, or no fair set among them.
        """
        if len(candidates) < self.count:
            raise NotEnoughEvents(
                f"only {len(candidates)} usable events, a puzzle needs {self.count}"
            )

        shuffled = list(candidates)
        random.Random(seed).shuffle(shuffled)

        chosen = self._search(shuffled, [])
        if chosen is None:
            raise NotEnoughEvents(
                f"no {self.count} of the {len(candidates)} usable events "
                "pass the fairness rules together"
            )
        return chosen

    def _search(self, remaining: Sequence[Event], chosen: list[Event]) -> list[Event] | None:
        """Depth-first: extend `chosen` from `remaining`, undoing picks that lead nowhere."""
        if len(chosen) == self.count:
            return chosen

        still_needed = self.count - len(chosen)
        for index, candidate in enumerate(remaining):
            if len(remaining) - index < still_needed:
                break
            if not self.checker.fits(candidate, chosen):
                continue

            found = self._search(remaining[index + 1 :], [*chosen, candidate])
            if found is not None:
                return found
        return None
