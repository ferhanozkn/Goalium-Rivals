import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.accounts.models import GuestSession


class GameSession(models.Model):
    KIND_CHOICES = (
        ("practice", "Practice"),
        ("live_1v1", "Live 1v1"),
        ("async_duel", "Async duel"),
        ("room", "Room"),
    )
    STATUS_CHOICES = (("waiting", "Waiting"), ("active", "Active"), ("finished", "Finished"), ("expired", "Expired"))
    LANGUAGE_CHOICES = (("tr", "Türkçe"), ("en", "English"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    modes = models.JSONField(default=list)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="tr")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="waiting")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Match(models.Model):
    TYPE_CHOICES = (("live_1v1", "Live 1v1"), ("practice", "Practice"), ("async_duel", "Async duel"), ("room", "Room"))
    ORIGIN_CHOICES = (("matchmaking", "Matchmaking"), ("invite", "Invite"), ("room", "Room"), ("practice", "Practice"))
    STATUS_CHOICES = (("waiting", "Waiting"), ("live", "Live"), ("finished", "Finished"), ("forfeit", "Forfeit"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game_session = models.OneToOneField(GameSession, on_delete=models.CASCADE, related_name="match")
    match_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="live_1v1")
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, default="invite")
    is_mixed = models.BooleanField(default=True)
    language = models.CharField(max_length=2, choices=GameSession.LANGUAGE_CHOICES, default="tr")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="waiting")
    max_players = models.PositiveSmallIntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    @property
    def ranked_eligible(self) -> bool:
        return self.match_type == "live_1v1" and self.is_mixed and self.origin == "matchmaking"


class MatchParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="match_participations")
    guest_session = models.ForeignKey(GuestSession, null=True, blank=True, on_delete=models.CASCADE, related_name="match_participations")
    display_name = models.CharField(max_length=80)
    score = models.IntegerField(default=0)
    connected = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["match", "user"], condition=Q(user__isnull=False), name="unique_user_per_match"),
            models.UniqueConstraint(fields=["match", "guest_session"], condition=Q(guest_session__isnull=False), name="unique_guest_per_match"),
        ]


class Round(models.Model):
    MODE_CHOICES = (
        ("hangman", "Hangman"),
        ("career_path", "Career path"),
        ("timed_trivia", "Timed trivia"),
        ("historical_score", "Historical score"),
        ("missing_lineup", "Missing lineup"),
    )
    STATUS_CHOICES = (("pending", "Pending"), ("active", "Active"), ("finished", "Finished"), ("timeout", "Timeout"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="rounds")
    question = models.ForeignKey("content.Question", null=True, blank=True, on_delete=models.PROTECT, related_name="rounds")
    order = models.PositiveSmallIntegerField()
    mode = models.CharField(max_length=24, choices=MODE_CHOICES)
    payload = models.JSONField(default=dict)
    private_state = models.JSONField(default=dict)
    deadline = models.DateTimeField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["match", "order"], name="unique_round_order")]


class Answer(models.Model):
    RESULT_CHOICES = (("correct", "Correct"), ("wrong", "Wrong"), ("timeout", "Timeout"), ("skipped", "Skipped"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="answers")
    participant = models.ForeignKey(MatchParticipant, on_delete=models.CASCADE, related_name="answers")
    raw_answer = models.TextField(blank=True)
    normalized_answer = models.TextField(blank=True)
    result = models.CharField(max_length=12, choices=RESULT_CHOICES)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    points = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["round", "participant"], name="unique_answer_per_round_participant")]
