"""Plain data passed between the generator's stages.

No network calls and no file IO here, so tests can build any of these by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

CC_BY_SA_NAME = "CC BY-SA 4.0"
CC_BY_SA_URL = "https://creativecommons.org/licenses/by-sa/4.0/"


@dataclass(frozen=True)
class Article:
    """A Wikipedia article an event links to.

    Players see these only after the reveal: article pages state the dates.
    """

    title: str
    url: str


@dataclass(frozen=True)
class Event:
    """One "On this day" entry."""

    year: int
    """Negative for BCE, as the feed sends it: -474 is 474 BCE."""

    text: str
    articles: tuple[Article, ...] = ()

    adapted: bool = False
    """True once the cleaner has changed `text`. CC BY-SA asks for changes to be
    indicated, so the attribution says "adapted" when any event is."""

    @property
    def year_label(self) -> str:
        """The year as a player reads it: `1812`, or `474 BCE`."""
        return f"{-self.year} BCE" if self.year < 0 else str(self.year)


@dataclass(frozen=True)
class Attribution:
    """Credit for the event text, which is CC BY-SA like all Wikipedia text."""

    source_url: str
    """The page the events come from, e.g. `Wikipedia:Selected anniversaries/October 13`."""

    adapted: bool
    source_name: str = 'Wikipedia, "On this day"'
    license_name: str = CC_BY_SA_NAME
    license_url: str = CC_BY_SA_URL

    @property
    def text(self) -> str:
        """One line to show during play."""
        lead = "Adapted from" if self.adapted else "From"
        return f"{lead} {self.source_name} ({self.license_name})"


@dataclass(frozen=True)
class Puzzle:
    """One day's puzzle, answer included."""

    puzzle_date: date
    feed: str
    """Which feed the events came from: `selected` or `events`."""

    events: tuple[Event, ...]
    """In chronological order: this tuple is the answer key. Shuffling them for
    the player is the game service's job."""

    attribution: Attribution
