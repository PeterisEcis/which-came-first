"""What `docker run IMAGE [COMMAND]` runs. The CI image job runs the real thing."""

from __future__ import annotations

import sys

from config.entrypoint import command_line

MANAGE = [sys.executable, "manage.py"]


class TestServe:
    def test_is_the_default(self) -> None:
        assert command_line([], {}) == command_line(["serve"], {})

    def test_listens_on_every_interface_at_port(self) -> None:
        program = command_line(["serve"], {"PORT": "8080"})

        assert program[:2] == ["gunicorn", "config.wsgi"]
        assert "--bind=0.0.0.0:8080" in program

    def test_falls_back_to_port_8000(self) -> None:
        assert "--bind=0.0.0.0:8000" in command_line(["serve"], {})

    def test_passes_extra_flags_to_gunicorn(self) -> None:
        assert command_line(["serve", "--workers=3"], {})[-1] == "--workers=3"


def test_migrate_never_waits_for_input() -> None:
    assert command_line(["migrate"], {}) == [*MANAGE, "migrate", "--no-input"]


def test_generate_runs_generate_puzzle_with_its_flags() -> None:
    assert command_line(["generate", "--date", "2026-10-20"], {}) == [
        *MANAGE,
        "generate_puzzle",
        "--date",
        "2026-10-20",
    ]


def test_anything_else_goes_to_manage_py() -> None:
    assert command_line(["createsuperuser"], {}) == [*MANAGE, "createsuperuser"]
