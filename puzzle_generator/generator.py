"""The generator: a date in, a puzzle out.

    fetch (feed.py) -> clean (cleaning.py) -> select (selection.py) -> Puzzle

Each stage is its own class and is handed in rather than built here, so a test
or a later feature can swap one without touching the others.
"""

from __future__ import annotations

import logging
from datetime import date

from puzzle_generator.cleaning import EventCleaner
from puzzle_generator.config import GeneratorSettings
from puzzle_generator.fairness import FairnessChecker
from puzzle_generator.feed import OnThisDayClient
from puzzle_generator.http_client import JsonFetcher
from puzzle_generator.models import Attribution, Puzzle
from puzzle_generator.selection import EventSelector

log = logging.getLogger(__name__)


class PuzzleGenerator:
    def __init__(
        self,
        feed: OnThisDayClient,
        cleaner: EventCleaner,
        selector: EventSelector,
    ) -> None:
        self.feed = feed
        self.cleaner = cleaner
        self.selector = selector

    @classmethod
    def from_settings(cls, settings: GeneratorSettings, http: JsonFetcher) -> PuzzleGenerator:
        checker = FairnessChecker.default(min_year_gap=settings.min_year_gap)
        return cls(
            feed=OnThisDayClient(http, feed=settings.feed),
            cleaner=EventCleaner(),
            selector=EventSelector(checker, count=settings.event_count),
        )

    def generate(self, day: date) -> Puzzle:
        """Build the puzzle for `day`.

        Raises:
            NotEnoughEvents: the day's events can't make a fair puzzle.
            FeedError: the feed's response was unusable.
            HttpError: the feed could not be reached.
        """
        fetched = self.feed.fetch(day)
        candidates = self.cleaner.clean(fetched)
        log.info("%s: %d of %d events usable after cleaning", day, len(candidates), len(fetched))

        # The seed includes the year, so 13 October 2026 and 2027 differ even
        # though the feed returns the same events for both.
        chosen = self.selector.select(candidates, seed=day.isoformat())
        events = tuple(sorted(chosen, key=lambda event: event.year))

        return Puzzle(
            puzzle_date=day,
            feed=self.feed.feed,
            events=events,
            attribution=Attribution(
                source_url=self.feed.source_page(day),
                adapted=any(event.adapted for event in events),
            ),
        )
