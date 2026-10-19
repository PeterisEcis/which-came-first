"""Health checks for whatever runs the container:

    GET /healthz   the process is up and answering: always 200
    GET /readyz    ... and can reach the database: 200, or 503 when it can't

A host restarts a container that fails /healthz, and holds traffic back from
one that fails /readyz. A database outage fails only /readyz: restarting the
server would not bring the database back.

Answered by a middleware at the top of the stack rather than by views. Probes
often send the container's IP address as Host, which ALLOWED_HOSTS rejects, and
they have no use for a player cookie.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase

logger = logging.getLogger(__name__)


class HealthCheckMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        if request.path == "/healthz":
            return plain(200, "ok")
        if request.path == "/readyz":
            return readiness()
        return self.get_response(request)


def readiness() -> HttpResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError as exc:
        # One line, not a traceback: a probe repeats this every few seconds for
        # as long as the outage lasts.
        logger.warning("readiness check: database unreachable: %s", exc)
        return plain(503, "database unreachable")
    return plain(200, "ok")


def plain(status: int, text: str) -> HttpResponse:
    return HttpResponse(text, status=status, content_type="text/plain")
