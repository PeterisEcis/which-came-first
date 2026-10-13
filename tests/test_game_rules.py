"""The rules of a round: feedback, status, and the share text. No database."""

from __future__ import annotations

from datetime import date

import pytest

from game.rules import InvalidGuess, PlayStatus, Referee, ShareText

ANSWER = ("a", "b", "c", "d", "e")
WRONG = ("b", "a", "c", "d", "e")

referee = Referee(ANSWER, max_attempts=4)


def test_marks_each_position_right_or_wrong() -> None:
    result = referee.check(["a", "c", "b", "d", "e"])

    assert result.correct == (True, False, False, True, True)
    assert not result.solved


def test_the_answer_solves_it() -> None:
    assert referee.check(ANSWER).solved


@pytest.mark.parametrize(
    "order",
    [
        [],
        ["a", "b", "c", "d"],
        ["a", "b", "c", "d", "e", "f"],
        ["a", "b", "c", "d", "x"],
        ["a", "a", "c", "d", "e"],
    ],
)
def test_a_guess_must_list_every_event_once(order: list[str]) -> None:
    with pytest.raises(InvalidGuess):
        referee.check(order)


def test_playing_until_solved() -> None:
    assert referee.status(referee.results([])) is PlayStatus.PLAYING
    assert referee.status(referee.results([WRONG])) is PlayStatus.PLAYING
    assert referee.status(referee.results([WRONG, ANSWER])) is PlayStatus.SOLVED


def test_solving_on_the_last_attempt_still_counts() -> None:
    assert referee.status(referee.results([WRONG, WRONG, WRONG, ANSWER])) is PlayStatus.SOLVED


def test_failed_once_attempts_run_out() -> None:
    assert referee.status(referee.results([WRONG] * 4)) is PlayStatus.FAILED


def test_attempts_left_counts_down_to_zero() -> None:
    assert referee.attempts_left(referee.results([])) == 4
    assert referee.attempts_left(referee.results([WRONG])) == 3
    assert referee.attempts_left(referee.results([WRONG] * 4)) == 0


class TestShareText:
    day = date(2026, 10, 13)

    def test_solved_shows_the_score_and_one_row_per_try(self) -> None:
        results = referee.results([WRONG, ANSWER])

        text = ShareText().build(self.day, results, PlayStatus.SOLVED, 4)

        assert text == "Which came first?\n2026-10-13 2/4\n⬜⬜🟩🟩🟩\n🟩🟩🟩🟩🟩"

    def test_failed_shows_an_x(self) -> None:
        results = referee.results([WRONG] * 4)

        text = ShareText().build(self.day, results, PlayStatus.FAILED, 4)

        assert text.splitlines()[:2] == ["Which came first?", "2026-10-13 X/4"]

    def test_names_no_event(self) -> None:
        text = ShareText().build(self.day, referee.results([ANSWER]), PlayStatus.SOLVED, 4)

        rows = text.split("\n", 2)[2]
        assert not [key for key in ANSWER if key in rows]
