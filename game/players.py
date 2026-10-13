"""Anonymous players: a random id in a cookie, no account needed.

Best-effort by design. Clearing cookies makes a new player with fresh attempts;
the bar is "no answers in the page source", not a fortress (todo.md, Step 2).
Accounts arrive in Step 10.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

from django.conf import settings
from django.http import HttpRequest
from django.http.response import HttpResponseBase

COOKIE_NAME = "player"

COOKIE_MAX_AGE = 400 * 24 * 60 * 60
"""400 days, the most browsers allow, so a streak (Step 6) can outlive a year."""


class PlayerRequest(HttpRequest):
    """An HttpRequest once PlayerCookieMiddleware has run. For type hints only."""

    player_id: UUID


class PlayerCookieMiddleware:
    """Gives every request a `player_id`, issuing a new cookie to new players."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        existing = self.read(request)
        cast(PlayerRequest, request).player_id = existing or uuid4()

        response = self.get_response(request)
        if existing is None:
            response.set_cookie(
                COOKIE_NAME,
                str(cast(PlayerRequest, request).player_id),
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=settings.SESSION_COOKIE_SECURE,
            )
        return response

    @staticmethod
    def read(request: HttpRequest) -> UUID | None:
        """The player id from the cookie, or None if missing or not a UUID."""
        try:
            return UUID(request.COOKIES.get(COOKIE_NAME, ""))
        except ValueError:
            return None
