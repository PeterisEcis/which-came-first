"""Fetching events from Wikipedia's "On this day" feed.

    GET https://en.wikipedia.org/api/rest_v1/feed/onthisday/{feed}/{MM}/{DD}

`selected` is the ~15-20 events picked for the Main Page; `events` is the full
list of ~50, noisier and with more repeated years. Both share one shape:

    {"selected": [{"text": "...", "year": 1812, "pages": [{...article summary...}]}]}

Each page is a whole article summary: extract, thumbnail and more. Only the
title and URL are kept. The extract usually states the date, and nothing that
can give the answer away should travel further than it has to.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from urllib.parse import quote

from puzzle_generator.http_client import JsonFetcher
from puzzle_generator.models import Article, Event

log = logging.getLogger(__name__)

FEED_URL = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/{feed}/{day:%m}/{day:%d}"
ARTICLE_URL = "https://en.wikipedia.org/wiki/{slug}"

SOURCE_PAGES = {
    "selected": "https://en.wikipedia.org/wiki/Wikipedia:Selected_anniversaries/{month}_{day}",
    "events": "https://en.wikipedia.org/wiki/{month}_{day}",
}
"""The page each feed is drawn from: what the attribution links to."""

FEED_TYPES = tuple(SOURCE_PAGES)

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""Spelled out rather than taken from strftime, whose month names follow the locale."""


class FeedError(RuntimeError):
    """The feed answered, but not with something usable."""


class OnThisDayClient:
    """Fetches one day's events and turns them into `Event`s."""

    def __init__(self, http: JsonFetcher, *, feed: str = "selected") -> None:
        if feed not in FEED_TYPES:
            raise ValueError(f"unknown feed {feed!r}; expected one of {', '.join(FEED_TYPES)}")
        self.http = http
        self.feed = feed

    def fetch(self, day: date) -> list[Event]:
        """Every well-formed event the feed lists for `day`.

        Only the month and day matter: the feed for 13 October is the same every
        year. Malformed entries are skipped rather than failing the run.

        Raises:
            FeedError: the response has no list of events under the expected key.
            HttpError: the request failed after retries.
        """
        url = self.feed_url(day)
        payload = self.http.get_json(url)

        entries = payload.get(self.feed)
        if not isinstance(entries, list):
            raise FeedError(f"{url} returned no {self.feed!r} list")

        events = [event for entry in entries if (event := self._to_event(entry)) is not None]
        log.info("%s: %d events in the %s feed", day, len(events), self.feed)
        return events

    def feed_url(self, day: date) -> str:
        return FEED_URL.format(feed=self.feed, day=day)

    def source_page(self, day: date) -> str:
        """The human-readable page this feed is drawn from, for the attribution."""
        return SOURCE_PAGES[self.feed].format(month=MONTH_NAMES[day.month - 1], day=day.day)

    @staticmethod
    def _to_event(entry: Any) -> Event | None:
        if not isinstance(entry, dict):
            return None

        year = entry.get("year")
        text = _text(entry.get("text"))
        # bool is a subclass of int; a stray `true` is not a year.
        if not isinstance(year, int) or isinstance(year, bool) or not text:
            log.debug("skipping a feed entry without a year or text")
            return None

        pages = entry.get("pages")
        articles = _to_articles(pages if isinstance(pages, list) else [])
        return Event(year=year, text=" ".join(text.split()), articles=articles)


def _to_articles(pages: list[Any]) -> tuple[Article, ...]:
    """Articles in feed order, each title once."""
    by_title: dict[str, Article] = {}
    for page in pages:
        article = _to_article(page)
        if article is not None:
            by_title.setdefault(article.title, article)
    return tuple(by_title.values())


def _to_article(page: Any) -> Article | None:
    if not isinstance(page, dict):
        return None

    # `titles.normalized` is plain text with spaces. `displaytitle` can hold
    # markup, and the bare `title` has underscores.
    titles = page.get("titles")
    title = _text(titles.get("normalized")) if isinstance(titles, dict) else ""
    title = title or _text(page.get("title")).replace("_", " ")
    if not title:
        return None

    url = _desktop_url(page) or ARTICLE_URL.format(slug=quote(title.replace(" ", "_")))
    return Article(title=title, url=url)


def _desktop_url(page: dict[str, Any]) -> str:
    urls = page.get("content_urls")
    desktop = urls.get("desktop") if isinstance(urls, dict) else None
    return _text(desktop.get("page")) if isinstance(desktop, dict) else ""


def _text(value: object) -> str:
    """`value` stripped if it is a string, else empty. Every feed field is optional."""
    return value.strip() if isinstance(value, str) else ""
