"""Command line entry point: `python -m puzzle_generator`.

Kept thin: parse arguments, configure logging, run the generator, and turn
exceptions into exit codes a workflow step can tell apart:

    0  success, or the date already had a puzzle
    1  unexpected failure, e.g. the feed was unreachable
    2  bad invocation (argparse)
    3  no fair puzzle can be built from the date's events
    4  configuration problem, e.g. no contact info

Nothing it logs or prints at the default level names an answer year, so a run in
a public CI log gives nothing away. `--stdout` prints the whole puzzle, answers
included, and is for local use.
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from puzzle_generator import __version__
from puzzle_generator.config import ConfigError, GeneratorSettings
from puzzle_generator.feed import FEED_TYPES, FeedError
from puzzle_generator.generator import PuzzleGenerator
from puzzle_generator.http_client import HttpClient, HttpError
from puzzle_generator.models import Puzzle
from puzzle_generator.selection import NotEnoughEvents
from puzzle_generator.serialization import PuzzleSerializer
from puzzle_generator.storage import PuzzleStore

log = logging.getLogger("puzzle_generator")

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_NO_PUZZLE = 3
EXIT_CONFIG = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="puzzle_generator",
        description="Build a 'which came first?' puzzle from Wikipedia's On this day feed.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--date",
        type=_parse_date,
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
        "--output-dir",
        type=Path,
        default=None,
        help="Where puzzle files go (default: output/puzzles, or WCF_OUTPUT_DIR)",
    )
    parser.add_argument(
        "--contact",
        default=None,
        help=(
            "Repo URL or email for the User-Agent. Required by Wikimedia policy; "
            "may also be set via WCF_CONTACT."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if the date already has a puzzle",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the puzzle JSON, answers included, instead of writing a file",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose", action="store_true", help="Log debug detail, including HTTP calls"
    )
    verbosity.add_argument(
        "-q", "--quiet", action="store_true", help="Log warnings and errors only"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(verbose=args.verbose, quiet=args.quiet)

    day: date = args.date or datetime.now(UTC).date()

    try:
        settings = GeneratorSettings.resolve(
            contact=args.contact,
            output_dir=args.output_dir,
            feed=args.feed,
        )
    except ConfigError as exc:
        log.error("%s", exc)
        return EXIT_CONFIG

    store = PuzzleStore(settings.output_dir)
    if not args.stdout and not args.force and store.exists(day):
        print(f"{day}: already generated, nothing to do ({store.path_for(day)})")
        return EXIT_OK

    try:
        puzzle = _generate(settings, day)
    except NotEnoughEvents as exc:
        log.error("%s: %s", day, exc)
        return EXIT_NO_PUZZLE
    except (FeedError, HttpError) as exc:
        log.error("%s", exc)
        return EXIT_FAILURE

    if args.stdout:
        _print_json(PuzzleSerializer().to_json(puzzle))
    else:
        path = store.save(puzzle)
        print(f"{day}: wrote {path} ({len(puzzle.events)} events)")
    return EXIT_OK


def _generate(settings: GeneratorSettings, day: date) -> Puzzle:
    with HttpClient(
        settings.user_agent,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries,
        backoff_factor=settings.backoff_factor,
    ) as http:
        return PuzzleGenerator.from_settings(settings, http).generate(day)


def _print_json(text: str) -> None:
    # Event text is not all ASCII. Piped output should be UTF-8, whatever the
    # console's code page.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(text)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from None


def _configure_logging(*, verbose: bool, quiet: bool) -> None:
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    # A console stuck on a legacy code page must not crash the run over an
    # accented letter in a log line.
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(errors="backslashreplace")

    logging.basicConfig(
        level=level,
        format="%(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    # urllib3 logs every retry at INFO, which drowns out our own output.
    logging.getLogger("urllib3").setLevel(logging.WARNING)


if __name__ == "__main__":
    raise SystemExit(main())
