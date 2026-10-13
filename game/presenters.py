"""What a player may see of a puzzle: the one place that decides when answers go out.

While a play is in progress the state holds event ids and text, and nothing
else about the events: no years, no article links (article pages state the
dates), no link to the source page (it lists every event with its year). All of
that sits under `reveal`, which stays None until the player solves the puzzle
or runs out of attempts.

The page and the API both send exactly this state, so keeping it answer-free
here keeps both answer-free.
"""

from __future__ import annotations

from typing import Any

from game.models import Play, Puzzle, PuzzleEvent
from game.rules import GuessResult, PlayStatus, Referee, ShareText


class PuzzleStatePresenter:
    def __init__(self, share: ShareText | None = None) -> None:
        self.share = share or ShareText()

    def present(self, puzzle: Puzzle, play: Play | None) -> dict[str, Any]:
        events = list(puzzle.events.all())
        referee = Referee(puzzle.answer_keys())
        results = referee.results(play.guesses if play else [])
        status = referee.status(results)
        credit = puzzle.attribution()

        return {
            "date": puzzle.date.isoformat(),
            "status": status.value,
            "max_attempts": referee.max_attempts,
            "attempts_left": referee.attempts_left(results),
            "events": [
                {"id": event.key, "text": event.text}
                for event in self._current_order(events, results)
            ],
            "guesses": [
                {"order": list(result.order), "correct": list(result.correct)} for result in results
            ],
            "credit": {"text": credit.text, "license_url": credit.license_url},
            "reveal": (
                None
                if status is PlayStatus.PLAYING
                else self._reveal(puzzle, events, results, status, referee.max_attempts)
            ),
        }

    @staticmethod
    def _current_order(events: list[PuzzleEvent], results: list[GuessResult]) -> list[PuzzleEvent]:
        """The starting order, or the player's last guess so they can adjust it."""
        if not results:
            return events
        by_key = {event.key: event for event in events}
        return [by_key[key] for key in results[-1].order]

    def _reveal(
        self,
        puzzle: Puzzle,
        events: list[PuzzleEvent],
        results: list[GuessResult],
        status: PlayStatus,
        max_attempts: int,
    ) -> dict[str, Any]:
        return {
            "events": [
                {
                    "id": event.key,
                    "text": event.text,
                    "year": event.year,
                    "year_label": event.year_label,
                    "articles": event.articles,
                }
                for event in sorted(events, key=lambda event: event.year)
            ],
            "source_url": puzzle.source_url,
            "share": self.share.build(puzzle.date, results, status, max_attempts),
        }
