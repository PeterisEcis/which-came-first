"""`python manage.py generate_puzzle`: build a date's puzzle and store it.

The Step 1 generator does the work; this command stores the result. It exits
with the same codes as `python -m puzzle_generator`, so a workflow step can tell
"no fair puzzle for this date" apart from "the feed is down". Like that CLI, it
never prints an answer year.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from game.importer import PuzzleImporter, PuzzleInUse
from game.models import Puzzle
from game.services import utc_today
from puzzle_generator.cli import EXIT_CONFIG, EXIT_FAILURE, EXIT_NO_PUZZLE
from puzzle_generator.config import ConfigError, GeneratorSettings
from puzzle_generator.feed import FEED_TYPES, FeedError
from puzzle_generator.generator import generate_puzzle
from puzzle_generator.http_client import HttpError
from puzzle_generator.models import Puzzle as GeneratedPuzzle
from puzzle_generator.selection import NotEnoughEvents


class Command(BaseCommand):
    help = "Generate the puzzle for a date (default: today, UTC) and store it in the database."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--date",
            type=date.fromisoformat,
            default=None,
            metavar="YYYY-MM-DD",
            help="Puzzle date (default: today, UTC)",
        )
        parser.add_argument(
            "--feed",
            choices=FEED_TYPES,
            default=None,
            help="selected: ~15-20 curated events; events: ~50, noisier (default: selected)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace the date's puzzle, as long as nobody has played it yet",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        day: date = options["date"] or utc_today()

        if not options["force"] and Puzzle.objects.filter(date=day).exists():
            self.stdout.write(f"{day}: already generated, nothing to do")
            return

        generated = self.generate(day, feed=options["feed"])
        try:
            PuzzleImporter().save(generated, replace=options["force"])
        except PuzzleInUse as exc:
            raise CommandError(str(exc), returncode=EXIT_FAILURE) from exc

        self.stdout.write(f"{day}: stored a puzzle of {len(generated.events)} events")

    @staticmethod
    def generate(day: date, *, feed: str | None) -> GeneratedPuzzle:
        try:
            generator_settings = GeneratorSettings.resolve(feed=feed)
        except ConfigError as exc:
            raise CommandError(str(exc), returncode=EXIT_CONFIG) from exc

        try:
            return generate_puzzle(generator_settings, day)
        except NotEnoughEvents as exc:
            raise CommandError(f"{day}: {exc}", returncode=EXIT_NO_PUZZLE) from exc
        except (FeedError, HttpError) as exc:
            raise CommandError(str(exc), returncode=EXIT_FAILURE) from exc
