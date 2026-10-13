"""The game's tables: puzzles, their events, and plays.

Events are stored with their years, so these rows hold the answers. What leaves
the server is decided in presenters.py, never by passing a model to a response.
"""

from __future__ import annotations

from django.db import models

from puzzle_generator.models import Attribution, year_label


class Puzzle(models.Model):
    date = models.DateField(unique=True)
    feed = models.CharField(max_length=20)
    """Which feed the events came from: `selected` or `events`."""

    source_url = models.URLField(max_length=500)
    """The page the events come from. It lists them with their years, so players
    get this link only after the reveal."""

    adapted = models.BooleanField(default=False)
    """Whether any event text was edited, for the CC BY-SA credit line."""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date",)

    def __str__(self) -> str:
        return f"Puzzle for {self.date}"

    def answer_keys(self) -> list[str]:
        """Event keys in chronological order: the answer."""
        return list(self.events.order_by("year").values_list("key", flat=True))

    def attribution(self) -> Attribution:
        return Attribution(source_url=self.source_url, adapted=self.adapted)


class PuzzleEvent(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="events")

    key = models.CharField(max_length=16)
    """Random public id, letters only. Never the primary key: ids handed out in
    chronological order would sort straight into the answer."""

    year = models.IntegerField()
    """Negative for BCE, as in the feed."""

    text = models.TextField()
    adapted = models.BooleanField(default=False)

    articles = models.JSONField(default=list)
    """`[{"title": ..., "url": ...}]`, shown after the reveal."""

    start_position = models.PositiveSmallIntegerField()
    """Where the event sits before the player moves anything. Shuffled once, at
    import, so every player starts from the same order."""

    class Meta:
        ordering = ("start_position",)
        constraints = (
            models.UniqueConstraint(fields=("puzzle", "key"), name="unique_event_key_per_puzzle"),
            models.UniqueConstraint(
                fields=("puzzle", "start_position"), name="unique_start_position_per_puzzle"
            ),
        )

    def __str__(self) -> str:
        return self.text

    @property
    def year_label(self) -> str:
        return year_label(self.year)


class Play(models.Model):
    """One player's go at one puzzle."""

    puzzle = models.ForeignKey(Puzzle, on_delete=models.PROTECT, related_name="plays")

    player_id = models.UUIDField()
    """From the anonymous player cookie (players.py)."""

    guesses = models.JSONField(default=list)
    """Each guess as the event keys in the order the player submitted them.
    Feedback is worked out again from these rather than stored."""

    solved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("puzzle", "player_id"), name="one_play_per_player_per_puzzle"
            ),
        )

    def __str__(self) -> str:
        return f"Player {self.player_id} on puzzle {self.puzzle_id}"
