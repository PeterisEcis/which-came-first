"""Game actions: finding a day's puzzle and recording guesses.

Views stay thin and call these. The rules themselves live in rules.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from game.models import Play, Puzzle
from game.rules import PlayStatus, Referee


def utc_today() -> date:
    """The game's current day. Puzzles roll over at 00:00 UTC."""
    return timezone.now().date()


class PuzzleNotFound(LookupError):
    """No puzzle is out for that date."""


class PlayFinished(RuntimeError):
    """The player has already solved the puzzle or used every attempt."""


class GameService:
    def todays_puzzle(self) -> Puzzle:
        return self.puzzle_for(utc_today())

    def puzzle_for(self, day: date) -> Puzzle:
        """The puzzle for `day`, if it is out.

        A future puzzle counts as missing: a guess at one would get feedback on
        an answer nobody should know yet.

        Raises:
            PuzzleNotFound: no puzzle for `day`, or `day` hasn't started.
        """
        if day > utc_today():
            raise PuzzleNotFound(f"no puzzle for {day}")
        try:
            return Puzzle.objects.get(date=day)
        except Puzzle.DoesNotExist:
            raise PuzzleNotFound(f"no puzzle for {day}") from None

    def play_for(self, puzzle: Puzzle, player_id: UUID) -> Play | None:
        return Play.objects.filter(puzzle=puzzle, player_id=player_id).first()

    def submit_guess(self, puzzle: Puzzle, player_id: UUID, order: Sequence[str]) -> Play:
        """Record `order` as the player's next guess.

        The attempt limit is enforced here, on the server: with per-position
        feedback and unlimited tries the puzzle would be trivially brute-forced.

        Raises:
            InvalidGuess: `order` isn't an ordering of the puzzle's events.
            PlayFinished: the player has no attempts left, or already solved it.
        """
        referee = Referee(puzzle.answer_keys())
        result = referee.check(order)  # before touching the database

        with transaction.atomic():
            # Locked, so two guesses sent at once can't both use the last attempt.
            play, _ = Play.objects.select_for_update().get_or_create(
                puzzle=puzzle, player_id=player_id
            )
            if referee.status(referee.results(play.guesses)) is not PlayStatus.PLAYING:
                raise PlayFinished("this puzzle is already finished")

            play.guesses = [*play.guesses, list(result.order)]
            play.solved = result.solved
            play.save(update_fields=["guesses", "solved", "updated_at"])
        return play
