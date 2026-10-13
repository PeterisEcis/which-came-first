"""`manage.py generate_puzzle`, run against the recorded 13 October feed."""

from __future__ import annotations

from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from django.core.management import CommandError, call_command

from fakes import feed_entry, feed_payload, load_fixture
from game.models import Play, Puzzle
from puzzle_generator.cli import EXIT_CONFIG, EXIT_FAILURE, EXIT_NO_PUZZLE
from puzzle_generator.http_client import HttpClient

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 13)


def serve(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    monkeypatch.setattr(HttpClient, "get_json", lambda self, url, params=None: payload)


@pytest.fixture(autouse=True)
def recorded_feed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No real network, no stray .env, and contact info unless a test removes it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WCF_CONTACT", "tests")
    serve(monkeypatch, load_fixture("onthisday_selected_10-13.json"))


def run(*args: str) -> str:
    output = StringIO()
    call_command("generate_puzzle", "--date", DAY.isoformat(), *args, stdout=output)
    return output.getvalue()


def test_stores_the_dates_puzzle() -> None:
    output = run()

    puzzle = Puzzle.objects.get(date=DAY)
    assert puzzle.events.count() == 5
    assert puzzle.feed == "selected"
    assert "stored a puzzle of 5 events" in output


def test_prints_no_answer_year() -> None:
    output = run()

    years = Puzzle.objects.get(date=DAY).events.values_list("year", flat=True)
    assert not [year for year in years if str(year) in output]


def test_a_second_run_leaves_the_puzzle_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    run()
    keys = Puzzle.objects.get(date=DAY).answer_keys()
    serve(monkeypatch, {})  # would fail if the feed were asked again

    output = run()

    assert "already generated" in output
    assert Puzzle.objects.get(date=DAY).answer_keys() == keys


def test_force_replaces_a_puzzle_nobody_has_played() -> None:
    run()
    keys = Puzzle.objects.get(date=DAY).answer_keys()

    run("--force")

    assert Puzzle.objects.get(date=DAY).answer_keys() != keys


def test_force_wont_replace_a_played_puzzle() -> None:
    run()
    Play.objects.create(puzzle=Puzzle.objects.get(date=DAY), player_id=uuid4())

    with pytest.raises(CommandError) as raised:
        run("--force")

    assert raised.value.returncode == EXIT_FAILURE


def test_no_fair_puzzle_has_its_own_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, feed_payload(feed_entry(1307, "Knights Templar are arrested.")))

    with pytest.raises(CommandError) as raised:
        run()

    assert raised.value.returncode == EXIT_NO_PUZZLE
    assert not Puzzle.objects.exists()


def test_missing_contact_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WCF_CONTACT")

    with pytest.raises(CommandError) as raised:
        run()

    assert raised.value.returncode == EXIT_CONFIG
