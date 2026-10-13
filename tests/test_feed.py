"""Reading the On this day feed into events."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from fakes import FakeHttp, feed_entry, feed_page, feed_payload
from puzzle_generator.feed import FeedError, OnThisDayClient
from puzzle_generator.models import Article, Event

DAY = date(2026, 10, 13)


def fetch(*entries: Any, feed: str = "selected") -> list[Event]:
    http = FakeHttp(feed_payload(*entries, feed=feed))
    return OnThisDayClient(http, feed=feed).fetch(DAY)


def test_reads_year_text_and_linked_articles() -> None:
    [event] = fetch(
        feed_entry(1307, "Hundreds of Knights Templar are arrested.", "Knights Templar")
    )

    assert event.year == 1307
    assert event.text == "Hundreds of Knights Templar are arrested."
    assert event.articles == (
        Article("Knights Templar", "https://en.wikipedia.org/wiki/Knights_Templar"),
    )
    assert not event.adapted


def test_keeps_bce_years_negative() -> None:
    [event] = fetch(feed_entry(-474, "A naval battle is fought off Cumae.", "Battle of Cumae"))

    assert event.year == -474
    assert event.year_label == "474 BCE"


def test_asks_for_the_days_feed_with_zero_padded_month_and_day() -> None:
    http = FakeHttp(feed_payload(feed="events"))

    client = OnThisDayClient(http, feed="events")
    client.fetch(date(2027, 3, 5))

    assert http.urls == ["https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/03/05"]


@pytest.mark.parametrize(
    ("feed", "page"),
    [
        ("selected", "https://en.wikipedia.org/wiki/Wikipedia:Selected_anniversaries/March_5"),
        ("events", "https://en.wikipedia.org/wiki/March_5"),
    ],
)
def test_source_page_is_the_page_the_feed_is_drawn_from(feed: str, page: str) -> None:
    assert OnThisDayClient(FakeHttp(), feed=feed).source_page(date(2027, 3, 5)) == page


def test_skips_malformed_entries() -> None:
    events = fetch(
        {"text": "No year at all."},
        {"year": 1500},
        {"year": True, "text": "A boolean is not a year."},
        {"year": "1500", "text": "Neither is a string."},
        feed_entry(1600, "   "),
        "not even an object",
        feed_entry(1700, "The one good entry."),
    )

    assert [event.year for event in events] == [1700]


def test_collapses_whitespace_in_text() -> None:
    [event] = fetch(feed_entry(1700, "  Spread \n across   lines. "))

    assert event.text == "Spread across lines."


def test_builds_an_article_url_when_the_feed_has_none() -> None:
    page = {"title": "Treaty_of_Utrecht"}
    [event] = fetch({"year": 1713, "text": "A treaty is signed.", "pages": [page]})

    assert event.articles == (
        Article("Treaty of Utrecht", "https://en.wikipedia.org/wiki/Treaty_of_Utrecht"),
    )


def test_lists_each_article_once() -> None:
    entry = feed_entry(1700, "Twice linked.", "Sweden", "Sweden", "Narva")

    [event] = fetch(entry)

    assert [article.title for article in event.articles] == ["Sweden", "Narva"]


def test_skips_pages_without_a_title() -> None:
    entry = {"year": 1700, "text": "One bad page.", "pages": [{}, feed_page("Narva")]}

    [event] = fetch(entry)

    assert [article.title for article in event.articles] == ["Narva"]


def test_response_without_the_feeds_list_is_an_error() -> None:
    client = OnThisDayClient(FakeHttp({"events": []}), feed="selected")

    with pytest.raises(FeedError, match="'selected'"):
        client.fetch(DAY)


def test_unknown_feed_is_rejected() -> None:
    with pytest.raises(ValueError, match="births"):
        OnThisDayClient(FakeHttp(), feed="births")
