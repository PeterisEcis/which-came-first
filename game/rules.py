"""The rules of a round, with no Django in sight.

A guess is the puzzle's event ids in the order the player put them. Feedback is
per position, Wordle-style: right or wrong for each place, never where a wrong
event belongs instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

MAX_ATTEMPTS = 4
"""Five events have 120 possible orders. With per-position feedback and unlimited
tries, anyone could work through them; with too few, a player who knows little
history is reduced to guessing. Four leaves room to reason from the feedback."""


class InvalidGuess(ValueError):
    """The guess is not an ordering of this puzzle's events."""


class PlayStatus(StrEnum):
    PLAYING = "playing"
    SOLVED = "solved"
    FAILED = "failed"


@dataclass(frozen=True)
class GuessResult:
    order: tuple[str, ...]
    correct: tuple[bool, ...]
    """One flag per position: is the event there the right one?"""

    @property
    def solved(self) -> bool:
        return all(self.correct)


class Referee:
    """Checks guesses against one puzzle's answer."""

    def __init__(self, answer: Sequence[str], *, max_attempts: int = MAX_ATTEMPTS) -> None:
        self.answer = tuple(answer)
        """Event ids in chronological order."""

        self.max_attempts = max_attempts

    def check(self, order: Sequence[str]) -> GuessResult:
        """Per-position feedback for `order`.

        Raises:
            InvalidGuess: `order` doesn't list every event exactly once.
        """
        guess = tuple(order)
        if len(guess) != len(self.answer) or set(guess) != set(self.answer):
            raise InvalidGuess("a guess must list every event exactly once")

        correct = tuple(
            guessed == expected for guessed, expected in zip(guess, self.answer, strict=True)
        )
        return GuessResult(guess, correct)

    def results(self, guesses: Iterable[Sequence[str]]) -> list[GuessResult]:
        return [self.check(guess) for guess in guesses]

    def status(self, results: Sequence[GuessResult]) -> PlayStatus:
        if results and results[-1].solved:
            return PlayStatus.SOLVED
        if len(results) >= self.max_attempts:
            return PlayStatus.FAILED
        return PlayStatus.PLAYING

    def attempts_left(self, results: Sequence[GuessResult]) -> int:
        return max(self.max_attempts - len(results), 0)


class ShareText:
    """The result a player can paste elsewhere, Wordle-style.

    One row of squares per guess, one square per position. It says how the
    player did without saying what the order is.
    """

    TITLE = "Which came first?"
    RIGHT = "🟩"
    WRONG = "⬜"

    def build(
        self,
        day: date,
        results: Sequence[GuessResult],
        status: PlayStatus,
        max_attempts: int,
    ) -> str:
        score = str(len(results)) if status is PlayStatus.SOLVED else "X"
        rows = [self._row(result) for result in results]
        return "\n".join([self.TITLE, f"{day.isoformat()} {score}/{max_attempts}", *rows])

    def _row(self, result: GuessResult) -> str:
        return "".join(self.RIGHT if correct else self.WRONG for correct in result.correct)
