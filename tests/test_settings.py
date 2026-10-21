"""Which database URL the settings pick, for the app and for `migrate`."""

from __future__ import annotations

from config.settings import LOCAL_DATABASE_URL, database_url

POOLED = "postgres://app@ep-x-pooler.example/db"
DIRECT = "postgres://app@ep-x.example/db"
NEON = {"DATABASE_URL": POOLED, "DATABASE_URL_UNPOOLED": DIRECT}


def test_the_app_goes_through_the_pooler() -> None:
    assert database_url(["manage.py", "runserver"], NEON) == POOLED
    assert database_url(["gunicorn", "config.wsgi"], NEON) == POOLED


def test_migrate_connects_directly() -> None:
    assert database_url(["manage.py", "migrate", "--no-input"], NEON) == DIRECT


def test_migrate_uses_database_url_without_a_direct_one() -> None:
    assert database_url(["manage.py", "migrate"], {"DATABASE_URL": POOLED}) == POOLED


def test_falls_back_to_the_compose_database() -> None:
    assert database_url(["manage.py", "migrate"], {}) == LOCAL_DATABASE_URL
