"""HTTP with the two behaviours the generator cannot do without.

1. A descriptive User-Agent. Wikimedia blocks generic ones, so the agent string
   is built from configured contact info rather than left to `requests`.
2. Retries. "External APIs will fail" is a design assumption, not a worry:
   idempotent GETs are retried with exponential backoff and honour Retry-After.

Carried over from the proverb app, minus the file download this one has no use for.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

RETRY_STATUSES = (429, 500, 502, 503, 504)
"""429 included deliberately: Wikimedia rate-limits, and backing off is correct."""


class HttpError(RuntimeError):
    """Any HTTP failure that survived the retry policy."""


class JsonFetcher(Protocol):
    """What the feed client needs from HTTP. Tests pass a fake instead."""

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...


class HttpClient:
    """A `requests.Session` configured for polite, resilient GETs."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 4,
        backoff_factor: float = 1.0,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._session = self._build_session(user_agent, max_retries, backoff_factor)

    @staticmethod
    def _build_session(
        user_agent: str, max_retries: int, backoff_factor: float
    ) -> requests.Session:
        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            status_forcelist=RETRY_STATUSES,
            backoff_factor=backoff_factor,
            allowed_methods=frozenset({"GET", "HEAD"}),
            respect_retry_after_header=True,
            # We raise our own error instead, so the message names the URL.
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)

        session = requests.Session()
        session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip"})
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET `url` and parse the response as a JSON object."""
        log.debug("GET %s params=%s", url, params)
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise HttpError(f"request to {url} failed: {exc}") from exc
        except ValueError as exc:
            raise HttpError(f"response from {url} was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise HttpError(f"expected a JSON object from {url}, got {type(payload).__name__}")
        return payload

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
