"""Writing puzzles to disk, and the JSON they become."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fakes import event
from puzzle_generator.models import Attribution, Puzzle
from puzzle_generator.storage import PuzzleStore

DAY = date(2026, 10, 13)


def puzzle(text: str = "Nero becomes Roman emperor.") -> Puzzle:
    return Puzzle(
        puzzle_date=DAY,
        feed="selected",
        events=(event(-474, "Battle of Cumae"), event(54, "Nero", text=text)),
        attribution=Attribution(source_url="https://en.wikipedia.org/wiki/X", adapted=False),
    )


def test_saves_one_file_per_date(tmp_path: Path) -> None:
    store = PuzzleStore(tmp_path)

    path = store.save(puzzle())

    assert path == tmp_path / "2026-10-13.json"
    assert store.exists(DAY)
    assert not store.exists(date(2026, 10, 14))


def test_file_holds_events_with_years_links_and_attribution(tmp_path: Path) -> None:
    path = PuzzleStore(tmp_path).save(puzzle())

    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["date"] == "2026-10-13"
    assert saved["feed"] == "selected"
    assert [e["year"] for e in saved["events"]] == [-474, 54]
    assert [e["year_label"] for e in saved["events"]] == ["474 BCE", "54"]
    assert saved["events"][1]["articles"] == [
        {"title": "Nero", "url": "https://en.wikipedia.org/wiki/Nero"}
    ]
    assert saved["attribution"]["license"] == "CC BY-SA 4.0"
    assert saved["attribution"]["text"] == 'From Wikipedia, "On this day" (CC BY-SA 4.0)'


def test_keeps_non_ascii_text_readable(tmp_path: Path) -> None:
    path = PuzzleStore(tmp_path).save(puzzle(text="Göta Canal opens."))

    assert "Göta Canal opens." in path.read_text(encoding="utf-8")


def test_saving_again_replaces_the_file_and_leaves_no_temp_files(tmp_path: Path) -> None:
    store = PuzzleStore(tmp_path)
    store.save(puzzle(text="First version."))

    path = store.save(puzzle(text="Second version."))

    assert "Second version." in path.read_text(encoding="utf-8")
    assert [p.name for p in tmp_path.iterdir()] == ["2026-10-13.json"]
