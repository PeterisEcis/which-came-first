"""The command line: exit codes, idempotency, and keeping answers out of the output."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from fakes import feed_entry, feed_payload
from puzzle_generator import cli
from puzzle_generator.http_client import HttpClient

FEED = feed_payload(
    feed_entry(1066, "William of Normandy wins at Hastings.", "Battle of Hastings"),
    feed_entry(1307, "Knights Templar are arrested across France.", "Knights Templar"),
    feed_entry(1492, "Columbus reaches the Bahamas.", "Christopher Columbus"),
    feed_entry(1582, "The Gregorian calendar skips this date in Italy.", "Gregorian calendar"),
    feed_entry(1792, "The cornerstone of the White House is laid.", "White House"),
    feed_entry(1884, "Greenwich is adopted as the prime meridian.", "Prime meridian"),
)
YEARS = ("1066", "1307", "1492", "1582", "1792", "1884")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No real network, no stray .env, and contact info unless a test removes it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WCF_CONTACT", "tests")
    monkeypatch.setenv("WCF_OUTPUT_DIR", str(tmp_path / "puzzles"))


def serve(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    monkeypatch.setattr(HttpClient, "get_json", lambda self, url, params=None: payload)


def run(*args: str) -> int:
    return cli.main(["--date", "2026-10-13", *args])


def test_writes_the_puzzle_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, FEED)

    assert run() == cli.EXIT_OK

    saved = json.loads((tmp_path / "puzzles" / "2026-10-13.json").read_text(encoding="utf-8"))
    assert len(saved["events"]) == 5


def test_a_second_run_leaves_the_puzzle_alone(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    serve(monkeypatch, FEED)
    run()
    serve(monkeypatch, {})  # would fail if the feed were asked again

    assert run() == cli.EXIT_OK
    assert "already generated" in capsys.readouterr().out


def test_force_regenerates(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, FEED)
    run()

    assert run("--force") == cli.EXIT_OK


def test_output_and_logs_name_no_answer_year(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    serve(monkeypatch, FEED)
    # By name: Django's logging config holds this logger at INFO.
    caplog.set_level(logging.DEBUG, logger="puzzle_generator")

    run("--verbose")

    captured = capsys.readouterr()
    shown = (captured.out + captured.err + caplog.text).replace(str(tmp_path), "<tmp>")
    assert not [year for year in YEARS if year in shown]


def test_stdout_prints_the_puzzle_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    serve(monkeypatch, FEED)

    assert run("--stdout") == cli.EXIT_OK

    assert json.loads(capsys.readouterr().out)["date"] == "2026-10-13"
    assert not (tmp_path / "puzzles").exists()


def test_missing_contact_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WCF_CONTACT")

    assert run() == cli.EXIT_CONFIG


def test_a_day_without_a_fair_puzzle_has_its_own_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, feed_payload(feed_entry(1307, "Knights Templar are arrested.")))

    assert run() == cli.EXIT_NO_PUZZLE


def test_an_unusable_feed_response_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, {"unexpected": "shape"})

    assert run() == cli.EXIT_FAILURE
