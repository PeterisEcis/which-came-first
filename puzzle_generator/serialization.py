"""A puzzle as JSON.

The JSON holds the answer -- each year sits next to its event -- so it is for
the server only, the same as the database row it turns into in Step 2.
"""

from __future__ import annotations

import json
from typing import Any

from puzzle_generator import __version__
from puzzle_generator.models import Article, Attribution, Event, Puzzle

FORMAT_VERSION = 1
"""Bump when the shape changes, so a loader can tell old files from new."""


class PuzzleSerializer:
    def to_json(self, puzzle: Puzzle) -> str:
        return json.dumps(self.to_dict(puzzle), ensure_ascii=False, indent=2) + "\n"

    def to_dict(self, puzzle: Puzzle) -> dict[str, Any]:
        return {
            "format": FORMAT_VERSION,
            "generator": f"which-came-first {__version__}",
            "date": puzzle.puzzle_date.isoformat(),
            "feed": puzzle.feed,
            "events": [self._event(event) for event in puzzle.events],
            "attribution": self._attribution(puzzle.attribution),
        }

    def _event(self, event: Event) -> dict[str, Any]:
        return {
            "year": event.year,
            "year_label": event.year_label,
            "text": event.text,
            "adapted": event.adapted,
            "articles": [self._article(article) for article in event.articles],
        }

    @staticmethod
    def _article(article: Article) -> dict[str, Any]:
        return {"title": article.title, "url": article.url}

    @staticmethod
    def _attribution(attribution: Attribution) -> dict[str, Any]:
        return {
            "text": attribution.text,
            "source_url": attribution.source_url,
            "license": attribution.license_name,
            "license_url": attribution.license_url,
            "adapted": attribution.adapted,
        }
