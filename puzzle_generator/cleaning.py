"""Cleaning event text so it doesn't give the answer away.

Two kinds of fix:

* Dropping. An event whose text names a year -- "War of 1812: ..." -- would
  hand out its own answer, or a neighbour's. It is dropped, not edited: cutting
  a year out of a sentence rarely leaves a good one.
* Editing. "(pictured)" points at the Main Page's image, which the puzzle does
  not show. It is removed, and the event marked as adapted.

The year patterns err towards dropping: "Flight 1549" goes along with "War of
1812". A lost candidate costs nothing; a leaked answer spoils the game.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import replace

from puzzle_generator.models import Event

log = logging.getLogger(__name__)

YEAR_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 1066, 1960s, 2004: four digits in the range most years fall in.
    re.compile(r"\b(?:1\d{3}|20\d{2})s?\b"),
    # 44 BC, 474 BCE, 79 AD, 79 CE
    re.compile(r"\b\d{1,4}\s*(?:BCE|BC|CE|AD)\b"),
    # AD 79
    re.compile(r"\bAD\s*\d{1,4}\b"),
)

IMAGE_REFERENCE = re.compile(r"\s*\((?:pictured|depicted)\b[^)]*\)", re.IGNORECASE)
"""`(pictured)`, `(pictured, left)` and friends, with the space before them."""


class EventCleaner:
    """Drops events that give a year away and tidies the text of the rest."""

    def clean(self, events: Iterable[Event]) -> list[Event]:
        cleaned = (self.clean_event(event) for event in events)
        return [event for event in cleaned if event is not None]

    def clean_event(self, event: Event) -> Event | None:
        """The event with its text tidied, or None if it can't be used."""
        text = self.strip_image_references(event.text)

        if not text:
            return None
        if self.names_a_year(text, event.year):
            log.debug("dropped, the text names a year: %s", text)
            return None

        if text == event.text:
            return event
        return replace(event, text=text, adapted=True)

    @staticmethod
    def strip_image_references(text: str) -> str:
        return IMAGE_REFERENCE.sub("", text).strip()

    @staticmethod
    def names_a_year(text: str, year: int) -> bool:
        """True if `text` mentions any year, or the event's own year in any form.

        The second check catches early years the patterns leave alone, like the
        476 in "In 476, Odoacer ...".
        """
        own_year = re.compile(rf"\b{abs(year)}\b")
        return any(pattern.search(text) for pattern in (*YEAR_PATTERNS, own_year))
