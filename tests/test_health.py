"""`/healthz` and `/readyz`, the probes a host sends the container."""

from __future__ import annotations

from typing import NoReturn

import pytest
from django.db import OperationalError, connection
from django.test import Client

from game.players import COOKIE_NAME


def unreachable() -> NoReturn:
    raise OperationalError("connection refused")


class TestHealthz:
    # No database fixture: a test that touched the database would fail.
    def test_answers_without_the_database(self, client: Client) -> None:
        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.content == b"ok"

    def test_answers_whatever_host_the_probe_sends(self, client: Client) -> None:
        assert client.get("/healthz", HTTP_HOST="10.0.0.7:8080").status_code == 200

    def test_sets_no_player_cookie(self, client: Client) -> None:
        assert COOKIE_NAME not in client.get("/healthz").cookies

    def test_stays_up_when_the_database_is_down(
        self, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(connection, "ensure_connection", unreachable)

        assert client.get("/healthz").status_code == 200


class TestReadyz:
    @pytest.mark.django_db
    def test_ready_when_the_database_answers(self, client: Client) -> None:
        response = client.get("/readyz")

        assert response.status_code == 200
        assert response.content == b"ok"

    def test_unavailable_when_the_database_is_down(
        self, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(connection, "ensure_connection", unreachable)

        response = client.get("/readyz")

        assert response.status_code == 503
        assert response.content == b"database unreachable"

    @pytest.mark.django_db
    def test_answers_whatever_host_the_probe_sends(self, client: Client) -> None:
        assert client.get("/readyz", HTTP_HOST="10.0.0.7:8080").status_code == 200


def test_only_the_exact_paths_skip_the_host_check(client: Client) -> None:
    assert client.get("/healthz/", HTTP_HOST="10.0.0.7:8080").status_code == 400
