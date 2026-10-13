"""The root URL map: the game at `/`, Django's admin site at `/admin/`."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("game.urls")),
]
