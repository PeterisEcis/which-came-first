from __future__ import annotations

from datetime import date

from django.urls import path, register_converter

from game.views import GuessApi, PuzzlePageView, TodayPuzzleApi


class IsoDateConverter:
    """`YYYY-MM-DD` in a URL. An impossible date like 2026-02-30 is a 404."""

    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value: str) -> date:
        return date.fromisoformat(value)  # ValueError makes Django skip the route

    def to_url(self, value: date) -> str:
        return value.isoformat()


register_converter(IsoDateConverter, "isodate")

app_name = "game"

urlpatterns = [
    path("", PuzzlePageView.as_view(), name="today"),
    path("api/puzzle/today", TodayPuzzleApi.as_view(), name="api-today"),
    path("api/puzzle/<isodate:day>/guess", GuessApi.as_view(), name="api-guess"),
]
