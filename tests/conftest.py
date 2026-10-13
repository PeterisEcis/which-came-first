"""Shared fixtures for the game tests."""

from __future__ import annotations

import random

import pytest

from fakes import generated_puzzle
from game.importer import PuzzleImporter
from game.models import Puzzle
from game.services import utc_today


@pytest.fixture
def puzzle(db: None) -> Puzzle:
    """Today's puzzle, stored the way `generate_puzzle` stores one."""
    return PuzzleImporter(random.Random(7)).save(generated_puzzle(utc_today()))


@pytest.fixture
def answer(puzzle: Puzzle) -> list[str]:
    """The puzzle's event ids in chronological order."""
    return puzzle.answer_keys()
