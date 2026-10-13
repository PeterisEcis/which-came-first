"""Settings for one generator run.

Values come from, in order of precedence:

1. CLI flags
2. real environment variables -- how CI will supply them
3. a `.env` file in the working directory -- for local runs; see `.env.example`
4. the defaults here

Once Django arrives (Step 2), its settings module can build these instead; the
generator only ever sees a `GeneratorSettings`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import dotenv_values

from puzzle_generator import __version__
from puzzle_generator.feed import FEED_TYPES

ENV_PREFIX = "WCF_"
DOTENV_PATH = Path(".env")
DEFAULT_OUTPUT_DIR = Path("output/puzzles")

MISSING_CONTACT_MESSAGE = (
    "No contact information configured. Wikimedia's User-Agent policy requires a "
    "descriptive agent that includes a way to reach the operator, and blocks "
    "requests that lack one.\n"
    "Set WCF_CONTACT in .env (copy .env.example to start one), or pass it per run:\n"
    "  --contact https://github.com/you/which-came-first"
)


class ConfigError(ValueError):
    """Settings are missing or unusable."""


@dataclass(frozen=True)
class GeneratorSettings:
    contact: str
    """Repo URL or email, embedded in the User-Agent.

    Required rather than defaulted on purpose: a silently generic agent fails
    with a confusing 403 much later.
    """

    output_dir: Path = DEFAULT_OUTPUT_DIR

    feed: str = "selected"
    """`selected` (~15-20 curated events a day) or `events` (~50, noisier)."""

    event_count: int = 5

    min_year_gap: int = 10
    """How close two events in one puzzle may be. 1812 against 1814 is a coin
    toss, not a question."""

    request_timeout: float = 30.0
    max_retries: int = 4
    backoff_factor: float = 1.0
    """Exponential backoff base, in seconds: 1, 2, 4, 8 ..."""

    @property
    def user_agent(self) -> str:
        return f"WhichCameFirst/{__version__} ({self.contact})"

    def merged_with(self, **overrides: object) -> GeneratorSettings:
        """A copy with the non-None overrides applied.

        Lets the CLI pass every flag through without caring which ones the user
        actually supplied.
        """
        supplied = {key: value for key, value in overrides.items() if value is not None}
        return replace(self, **supplied)  # type: ignore[arg-type]

    @classmethod
    def resolve(
        cls,
        env: Mapping[str, str] | None = None,
        **overrides: object,
    ) -> GeneratorSettings:
        """Build settings from the environment, with CLI flags taking precedence.

        `overrides` are the CLI's flags; None means "not supplied". `env`
        defaults to `read_environment()`; tests pass a mapping instead.

        Raises:
            ConfigError: no contact information, or an unknown feed.
        """
        source = read_environment() if env is None else env

        from_env = cls(
            contact=source.get(f"{ENV_PREFIX}CONTACT", "").strip(),
            output_dir=Path(source.get(f"{ENV_PREFIX}OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))),
            feed=source.get(f"{ENV_PREFIX}FEED", "selected").strip(),
        )

        # Checked after merging, so a flag can still settle them.
        settings = from_env.merged_with(**overrides)
        if not settings.contact.strip():
            raise ConfigError(MISSING_CONTACT_MESSAGE)
        if settings.feed not in FEED_TYPES:
            raise ConfigError(
                f"{ENV_PREFIX}FEED must be one of {', '.join(FEED_TYPES)}, got {settings.feed!r}"
            )
        return settings


def read_environment(dotenv_path: Path = DOTENV_PATH) -> dict[str, str]:
    """The process environment, with `dotenv_path` filling in whatever it lacks.

    Real environment variables win, so a value set in CI is never overridden by
    a stray `.env` file. A missing file is fine: CI has none.
    """
    values = dotenv_values(dotenv_path)
    # A bare `KEY` line with no `=` parses as None; treat it as absent.
    from_file = {key: value for key, value in values.items() if value is not None}
    return {**from_file, **os.environ}
