import uuid

from django.conf import settings
from django.db import models


class Rating(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rating")
    rating = models.PositiveIntegerField(default=1000)
    matches_played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "-matches_played", "user__display_name"]

    @property
    def in_placement(self) -> bool:
        return self.matches_played < 10


class RatingEvent(models.Model):
    OUTCOME_CHOICES = (("win", "Win"), ("draw", "Draw"), ("loss", "Loss"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey("quiz.Match", on_delete=models.PROTECT, related_name="rating_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rating_events")
    previous_rating = models.IntegerField()
    new_rating = models.IntegerField()
    delta = models.IntegerField()
    outcome = models.CharField(max_length=8, choices=OUTCOME_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "user_id"]
        constraints = [
            models.UniqueConstraint(fields=["match", "user"], name="unique_rating_event_match_user"),
        ]


class LeaderboardSnapshot(models.Model):
    PERIOD_CHOICES = (("global", "Global"), ("season", "Season"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(max_length=12, choices=PERIOD_CHOICES)
    period_key = models.CharField(max_length=16)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leaderboard_snapshots")
    rank = models.PositiveIntegerField()
    rating = models.PositiveIntegerField()
    matches_played = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["period", "period_key", "rank"]
        constraints = [
            models.UniqueConstraint(fields=["period", "period_key", "user"], name="unique_leaderboard_snapshot_user"),
        ]
