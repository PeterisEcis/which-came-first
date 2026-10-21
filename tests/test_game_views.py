"""The page and the JSON API, through Django's test client."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

import pytest
from django.http import HttpResponse
from django.test import Client
from pytest_django import Settings

from fakes import ANSWER_YEARS, SOURCE_URL, generated_puzzle
from game.importer import PuzzleImporter
from game.models import Play, Puzzle
from game.players import COOKIE_MAX_AGE, COOKIE_NAME
from game.services import utc_today

pytestmark = pytest.mark.django_db

PAGE = "/"
TODAY_API = "/api/puzzle/today"


def guess_url(day: date) -> str:
    return f"/api/puzzle/{day.isoformat()}/guess"


def guess(client: Client, puzzle: Puzzle, order: list[str]) -> HttpResponse:
    return client.post(
        guess_url(puzzle.date), data=json.dumps({"order": order}), content_type="application/json"
    )


def all_wrong(answer: list[str]) -> list[str]:
    """Every event one place off: no position right."""
    return answer[1:] + answer[:1]


def embedded_state(page: HttpResponse) -> dict[str, Any]:
    match = re.search(
        r'<script id="puzzle-state" type="application/json">(.*?)</script>', page.text, re.S
    )
    assert match, "the page has no embedded state"
    state: dict[str, Any] = json.loads(match.group(1))
    return state


def leaked(body: str) -> list[str]:
    """Anything in `body` that gives the answer away before the reveal."""
    secrets = [str(year) for year in ANSWER_YEARS] + ["Article_", "Article ", SOURCE_URL]
    return [secret for secret in secrets if secret in body]


class TestTodayApi:
    def test_sends_events_without_their_years(self, client: Client, puzzle: Puzzle) -> None:
        state = client.get(TODAY_API).json()

        assert state["status"] == "playing"
        assert (state["attempts_left"], state["max_attempts"]) == (4, 4)
        assert state["guesses"] == []
        assert all(set(event) == {"id", "text"} for event in state["events"])
        assert state["reveal"] is None

    def test_starts_everyone_from_the_same_shuffled_order(
        self, client: Client, puzzle: Puzzle
    ) -> None:
        first = client.get(TODAY_API).json()["events"]
        second = Client().get(TODAY_API).json()["events"]

        assert first == second
        assert [event["id"] for event in first] == [event.key for event in puzzle.events.all()]

    def test_credits_wikipedia_without_linking_the_source_page(
        self, client: Client, puzzle: Puzzle
    ) -> None:
        credit = client.get(TODAY_API).json()["credit"]

        assert credit["text"] == 'From Wikipedia, "On this day" (CC BY-SA 4.0)'
        assert credit["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"

    def test_no_puzzle_today_is_a_404(self, client: Client, db: None) -> None:
        response = client.get(TODAY_API)

        assert response.status_code == 404
        assert "no puzzle" in response.json()["error"]


class TestNoAnswersBeforeTheReveal:
    """The Step 2 promise, and the invariant Step 3's CI leak test will hold."""

    @pytest.mark.parametrize("url", [PAGE, TODAY_API])
    def test_not_before_the_first_guess(self, client: Client, puzzle: Puzzle, url: str) -> None:
        assert leaked(client.get(url).text) == []

    @pytest.mark.parametrize("url", [PAGE, TODAY_API])
    def test_not_after_wrong_guesses(
        self, client: Client, puzzle: Puzzle, answer: list[str], url: str
    ) -> None:
        for _ in range(3):
            assert leaked(guess(client, puzzle, all_wrong(answer)).text) == []

        assert leaked(client.get(url).text) == []

    def test_but_yes_once_solved(self, client: Client, puzzle: Puzzle, answer: list[str]) -> None:
        # Proves the checks above can see a leak: here the answer is allowed out.
        guess(client, puzzle, answer)

        assert leaked(client.get(PAGE).text) != []


class TestGuessing:
    def test_a_guess_gets_per_position_feedback(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        order = [answer[0], answer[2], answer[1], answer[3], answer[4]]

        state = guess(client, puzzle, order).json()

        assert state["guesses"] == [{"order": order, "correct": [True, False, False, True, True]}]
        assert (state["status"], state["attempts_left"]) == ("playing", 3)
        assert state["reveal"] is None

    def test_the_next_try_starts_from_the_last_guess(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        order = all_wrong(answer)
        guess(client, puzzle, order)

        state = client.get(TODAY_API).json()

        assert [event["id"] for event in state["events"]] == order

    def test_solving_reveals_years_links_and_the_source(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        state = guess(client, puzzle, answer).json()

        assert state["status"] == "solved"
        reveal = state["reveal"]
        assert [event["year"] for event in reveal["events"]] == list(ANSWER_YEARS)
        assert [event["id"] for event in reveal["events"]] == answer
        assert reveal["events"][0]["articles"][0]["title"] == "Article 1066"
        assert reveal["source_url"] == SOURCE_URL
        assert reveal["share"].startswith(f"Which came first?\n{puzzle.date.isoformat()} 1/4\n")

    def test_running_out_of_attempts_reveals_the_answer(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        for _ in range(4):
            state = guess(client, puzzle, all_wrong(answer)).json()

        assert state["status"] == "failed"
        assert state["attempts_left"] == 0
        assert [event["year"] for event in state["reveal"]["events"]] == list(ANSWER_YEARS)
        assert "X/4" in state["reveal"]["share"]

    def test_no_more_guesses_once_solved(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        guess(client, puzzle, answer)

        assert guess(client, puzzle, answer).status_code == 409

    def test_no_more_guesses_once_out_of_attempts(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        for _ in range(4):
            guess(client, puzzle, all_wrong(answer))

        response = guess(client, puzzle, answer)

        assert response.status_code == 409
        assert Play.objects.get().guesses[-1] != answer

    def test_each_player_has_their_own_attempts(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        guess(client, puzzle, answer)

        assert Client().get(TODAY_API).json()["status"] == "playing"

    @pytest.mark.parametrize(
        "body", ["not json", "[]", '{"order": "abcde"}', '{"order": [1, 2, 3, 4, 5]}', "{}"]
    )
    def test_a_malformed_body_is_a_400(self, client: Client, puzzle: Puzzle, body: str) -> None:
        response = client.post(guess_url(puzzle.date), data=body, content_type="application/json")

        assert response.status_code == 400

    def test_an_order_that_isnt_every_event_once_is_a_400(
        self, client: Client, puzzle: Puzzle, answer: list[str]
    ) -> None:
        response = guess(client, puzzle, [answer[0]] * 5)

        assert response.status_code == 400
        assert not Play.objects.exists()

    def test_a_future_puzzle_cant_be_guessed_even_if_stored(self, client: Client, db: None) -> None:
        tomorrow = utc_today() + timedelta(days=1)
        puzzle = PuzzleImporter().save(generated_puzzle(tomorrow))

        response = guess(client, puzzle, puzzle.answer_keys())

        assert response.status_code == 404
        assert not Play.objects.exists()

    def test_a_date_without_a_puzzle_is_a_404(self, client: Client, db: None) -> None:
        response = client.post(
            guess_url(date(2020, 1, 1)), data='{"order": []}', content_type="application/json"
        )

        assert response.status_code == 404

    def test_an_impossible_date_is_a_404(self, client: Client, db: None) -> None:
        response = client.post("/api/puzzle/2026-02-30/guess", data="{}", content_type="text/plain")

        assert response.status_code == 404


class TestPage:
    def test_embeds_the_same_state_as_the_api(self, client: Client, puzzle: Puzzle) -> None:
        page = client.get(PAGE)

        assert page.status_code == 200
        assert embedded_state(page) == client.get(TODAY_API).json()

    def test_no_puzzle_today_is_a_friendly_404(self, client: Client, db: None) -> None:
        page = client.get(PAGE)

        assert page.status_code == 404
        assert "no puzzle" in page.text

    @pytest.mark.parametrize("url", [PAGE, TODAY_API])
    def test_responses_are_never_cached(self, client: Client, puzzle: Puzzle, url: str) -> None:
        # They depend on the player's cookie; a shared cache would mix players up.
        assert "no-store" in client.get(url)["Cache-Control"]


class TestPlayerCookie:
    def test_a_new_player_gets_an_http_only_cookie(self, client: Client, puzzle: Puzzle) -> None:
        cookie = client.get(PAGE).cookies[COOKIE_NAME]

        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"
        assert cookie["max-age"] == COOKIE_MAX_AGE

    def test_a_returning_player_keeps_theirs(self, client: Client, puzzle: Puzzle) -> None:
        client.get(PAGE)

        assert COOKIE_NAME not in client.get(PAGE).cookies

    def test_a_garbled_cookie_is_replaced(self, client: Client, puzzle: Puzzle) -> None:
        client.cookies[COOKIE_NAME] = "not-a-uuid"

        assert COOKIE_NAME in client.get(PAGE).cookies


class TestCsrf:
    def test_a_guess_without_the_token_is_refused(self, puzzle: Puzzle, answer: list[str]) -> None:
        client = Client(enforce_csrf_checks=True)
        client.get(PAGE)

        assert guess(client, puzzle, answer).status_code == 403

    def test_a_guess_with_the_token_from_the_page_goes_through(
        self, puzzle: Puzzle, answer: list[str]
    ) -> None:
        client = Client(enforce_csrf_checks=True)
        client.get(PAGE)
        token = client.cookies["csrftoken"].value

        response = client.post(
            guess_url(puzzle.date),
            data=json.dumps({"order": answer}),
            content_type="application/json",
            headers={"X-CSRFToken": token},
        )

        assert response.status_code == 200

    def test_through_an_https_proxy_a_guess_goes_through(
        self, settings: Settings, puzzle: Puzzle, answer: list[str]
    ) -> None:
        # What config/settings.py sets when DJANGO_BEHIND_HTTPS_PROXY=1.
        settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

        assert guess_through_an_https_proxy(puzzle, answer).status_code == 200

    def test_through_an_https_proxy_not_trusted_a_guess_is_refused(
        self, puzzle: Puzzle, answer: list[str]
    ) -> None:
        # Django takes the request for http://, which the https:// Origin doesn't match.
        assert guess_through_an_https_proxy(puzzle, answer).status_code == 403


def guess_through_an_https_proxy(puzzle: Puzzle, order: list[str]) -> HttpResponse:
    """A browser's guess as Cloud Run's front end passes it on: in plain HTTP,
    with the browser's https:// Origin and X-Forwarded-Proto saying it was HTTPS."""
    client = Client(enforce_csrf_checks=True)
    client.get(PAGE)
    return client.post(
        guess_url(puzzle.date),
        data=json.dumps({"order": order}),
        content_type="application/json",
        headers={
            "X-CSRFToken": client.cookies["csrftoken"].value,
            # As a browser sends it. Without Host the test client falls back to
            # its server port, 80, which isn't HTTPS's: the host would become
            # testserver:80 and match no Origin.
            "Host": "testserver",
            "Origin": "https://testserver",
            "X-Forwarded-Proto": "https",
        },
    )
