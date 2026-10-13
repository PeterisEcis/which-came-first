"""Django's built-in admin, for looking at puzzles and plays while developing.

Shows the answers, so it's for superusers only (`manage.py createsuperuser`).
The real admin panel, with roles and puzzle approval, is Step 11.
"""

from __future__ import annotations

from django.contrib import admin

from game.models import Play, Puzzle, PuzzleEvent


class PuzzleEventInline(admin.TabularInline[PuzzleEvent, Puzzle]):
    model = PuzzleEvent
    fields = ("start_position", "year", "text", "key")
    readonly_fields = ("key",)
    extra = 0


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin[Puzzle]):
    list_display = ("date", "feed", "adapted", "created_at")
    inlines = (PuzzleEventInline,)


@admin.register(Play)
class PlayAdmin(admin.ModelAdmin[Play]):
    list_display = ("puzzle", "player_id", "solved", "attempts", "updated_at")
    list_filter = ("solved",)

    @admin.display(description="attempts")
    def attempts(self, play: Play) -> int:
        return len(play.guesses)
