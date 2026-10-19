"""Shared fixtures for the game tests."""

from __future__ import annotations

import random

import pytest
from pytest_django import Settings

from fakes import generated_puzzle
from game.importer import PuzzleImporter
from game.models import Puzzle
from game.services import utc_today


@pytest.fixture(autouse=True)
def static_files_without_a_manifest(settings: Settings) -> None:
    """Plain `/static/...` URLs, not the hashed ones production serves.

    Production looks every file up in the manifest that `collectstatic` writes,
    and only the image build runs that. The CI image job checks the hashed URLs
    against the real container.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    # WhiteNoise finds the files in each app's static/ folder, as under
    # runserver, rather than warning that collectstatic's folder is missing.
    settings.WHITENOISE_AUTOREFRESH = True


@pytest.fixture
def puzzle(db: None) -> Puzzle:
    """Today's puzzle, stored the way `generate_puzzle` stores one."""
    return PuzzleImporter(random.Random(7)).save(generated_puzzle(utc_today()))


@pytest.fixture
def answer(puzzle: Puzzle) -> list[str]:
    """The puzzle's event ids in chronological order."""
    return puzzle.answer_keys()
