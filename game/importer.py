"""Storing a generated puzzle in the database.

Two things are decided here, once, so every player gets the same puzzle:

* The starting order: shuffled, but never already sorted, or submitting
  without moving anything would win.
* Each event's public key: random letters. Nothing a player can see should sort
  into the answer the way sequential ids would, or look like a year.
"""

from __future__ import annotations

import random
import string
from datetime import date

from django.db import transaction

from game.models import Puzzle, PuzzleEvent
from puzzle_generator.models import Puzzle as GeneratedPuzzle

KEY_ALPHABET = string.ascii_letters
KEY_LENGTH = 8


class PuzzleExists(RuntimeError):
    """The date already has a puzzle, and replacing it wasn't asked for."""


class PuzzleInUse(RuntimeError):
    """The date's puzzle has been played, so it can no longer be replaced."""


class PuzzleImporter:
    def __init__(self, rng: random.Random | None = None) -> None:
        # SystemRandom by default: start orders and keys shouldn't be predictable.
        # Tests pass a seeded Random instead.
        self.rng = rng or random.SystemRandom()

    def save(self, generated: GeneratedPuzzle, *, replace: bool = False) -> Puzzle:
        """Store `generated` as its date's puzzle.

        Raises:
            PuzzleExists: the date has a puzzle and `replace` is False.
            PuzzleInUse: the date's puzzle has plays; replacing it would change
                the answer under those players.
        """
        events = sorted(generated.events, key=lambda event: event.year)
        positions = self.start_positions(len(events))
        keys = self.event_keys(len(events))

        with transaction.atomic():
            self._clear(generated.puzzle_date, replace=replace)
            puzzle = Puzzle.objects.create(
                date=generated.puzzle_date,
                feed=generated.feed,
                source_url=generated.attribution.source_url,
                adapted=generated.attribution.adapted,
            )
            PuzzleEvent.objects.bulk_create(
                PuzzleEvent(
                    puzzle=puzzle,
                    key=key,
                    year=event.year,
                    text=event.text,
                    adapted=event.adapted,
                    articles=[{"title": a.title, "url": a.url} for a in event.articles],
                    start_position=position,
                )
                for event, key, position in zip(events, keys, positions, strict=True)
            )
        return puzzle

    def start_positions(self, count: int) -> list[int]:
        """Where each event starts, by chronological index. Never the identity.

        `positions[i]` is the starting place of the i-th earliest event.
        """
        if count < 2:
            raise ValueError(f"a puzzle needs at least 2 events to shuffle, got {count}")

        in_order = list(range(count))
        positions = list(in_order)
        while positions == in_order:
            self.rng.shuffle(positions)
        return positions

    def event_keys(self, count: int) -> list[str]:
        keys: list[str] = []
        while len(keys) < count:
            key = "".join(self.rng.choices(KEY_ALPHABET, k=KEY_LENGTH))
            if key not in keys:
                keys.append(key)
        return keys

    @staticmethod
    def _clear(day: date, *, replace: bool) -> None:
        existing = Puzzle.objects.filter(date=day).first()
        if existing is None:
            return
        if not replace:
            raise PuzzleExists(f"{day} already has a puzzle")
        if existing.plays.exists():
            raise PuzzleInUse(f"{day}'s puzzle has been played, so it can't be replaced")
        existing.delete()
