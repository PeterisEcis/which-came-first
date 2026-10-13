"""Stand-ins for the network, and builders for feed responses and events.

Nothing here talks to Wikipedia. Feed responses come from one of two places:
recorded from the real feed into `fixtures/`, so the happy path is tested
against what Wikipedia actually sends, or built by hand for an edge case. The
builders cut the shape down to the fields the generator reads, plus an extract.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from puzzle_generator.models import Article, Attribution, Event, Puzzle

FIXTURES = Path(__file__).parent / "fixtures"

ANSWER_YEARS = (1066, 1307, 1492, 1588, 1815)
"""The years in `generated_puzzle`. None of them appears in a date this decade,
so finding one in a response means an answer leaked."""

SOURCE_URL = "https://en.wikipedia.org/wiki/Wikipedia:Selected_anniversaries/October_13"


def load_fixture(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


class FakeHttp:
    """Plays the part of `HttpClient`.

    `get_json` answers with the given payloads in order, raising any that is an
    exception. Every requested URL is recorded.
    """

    def __init__(self, *payloads: dict[str, Any] | Exception) -> None:
        self._payloads = iter(payloads)
        self.urls: list[str] = []

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.urls.append(url)
        payload = next(self._payloads, None)
        if payload is None:
            raise AssertionError(f"unexpected request #{len(self.urls)} to {url}")
        if isinstance(payload, Exception):
            raise payload
        return payload


def feed_page(title: str) -> dict[str, Any]:
    """One entry of an event's `pages` list, shaped like the real summary."""
    slug = title.replace(" ", "_")
    return {
        "type": "standard",
        "title": slug,
        "displaytitle": f'<span class="mw-page-title-main">{title}</span>',
        "titles": {"canonical": slug, "normalized": title, "display": title},
        "content_urls": {
            "desktop": {"page": f"https://en.wikipedia.org/wiki/{slug}"},
            "mobile": {"page": f"https://en.m.wikipedia.org/wiki/{slug}"},
        },
        "extract": f"{title} took place in a year this extract gives away.",
    }


def feed_entry(year: int, text: str, *links: str) -> dict[str, Any]:
    return {"text": text, "year": year, "pages": [feed_page(title) for title in links]}


def feed_payload(*entries: dict[str, Any], feed: str = "selected") -> dict[str, Any]:
    return {feed: list(entries)}


def generated_puzzle(day: date) -> Puzzle:
    """A five-event puzzle as the generator would hand it over.

    Each event links an article whose title contains its year, the way
    "Siege of Port Royal (1710)" does in the real feed, so a leaked link shows
    up as a leaked year.
    """
    return Puzzle(
        puzzle_date=day,
        feed="selected",
        events=tuple(
            event(year, f"Article {year}", text=f"Something notable happened, part {letter}")
            for year, letter in zip(ANSWER_YEARS, "ABCDE", strict=True)
        ),
        attribution=Attribution(source_url=SOURCE_URL, adapted=False),
    )


def event(year: int, *links: str, text: str = "") -> Event:
    """An event for tests that only care about its year and links."""
    return Event(
        year=year,
        text=text or f"Something happened, event number {year % 97}",
        articles=tuple(
            Article(title, f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
            for title in links
        ),
    )
