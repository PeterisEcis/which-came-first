"""Health checks for whatever runs the container:

    GET /health   the process is up and answering: always 200
    GET /ready    ... and can reach the database: 200, or 503 when it can't

A host restarts a container that fails /health, and holds traffic back from
one that fails /ready. A database outage fails only /ready: restarting the
server would not bring the database back.

Not the customary /healthz and /readyz: Cloud Run's front end keeps some paths
ending in "z" for itself and answers them with its own 404, so a check from
outside, like the post-deploy smoke test, never reaches the container.

Answered by a middleware at the top of the stack rather than by views. Probes
often send the container's IP address as Host, which ALLOWED_HOSTS rejects, and
they have no use for a player cookie.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase

logger = logging.getLogger(__name__)


class HealthCheckMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        if request.path == "/health":
            return plain(200, "ok")
        if request.path == "/ready":
            return readiness()
        return self.get_response(request)


def readiness() -> HttpResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    # ImproperlyConfigured too: a DATABASE_URL without a database name parses,
    # then fails only here, at the first connection.
    except (DatabaseError, ImproperlyConfigured) as exc:
        # One line, not a traceback: a probe repeats this every few seconds for
        # as long as the outage lasts.
        logger.warning("readiness check: database unreachable: %s", exc)
        return plain(503, "database unreachable")
    return plain(200, "ok")


def plain(status: int, text: str) -> HttpResponse:
    return HttpResponse(text, status=status, content_type="text/plain")
