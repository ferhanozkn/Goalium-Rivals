import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.content.constants import (
    DIFFICULTY_CHOICES,
    LANGUAGE_CHOICES,
    MODE_CHOICES,
    QUESTION_STATUS_CHOICES,
    SOURCE_LICENSE_STATUS_CHOICES,
)


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SourceReference(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=80)
    url = models.URLField(max_length=500)
    license_name = models.CharField(max_length=160)
    license_status = models.CharField(max_length=12, choices=SOURCE_LICENSE_STATUS_CHOICES, default="pending")
    accessed_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-accessed_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "url"], name="unique_source_provider_url"),
        ]

    def __str__(self) -> str:
        return f"{self.provider}: {self.url}"


class Competition(TimestampedModel):
    KIND_CHOICES = (("league", "League"), ("cup", "Cup"), ("international", "International"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=160, unique=True)
    name = models.CharField(max_length=160)
    country_code = models.CharField(max_length=3, blank=True)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="league")
    source_url = models.URLField(max_length=500, blank=True)
    source_license = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Season(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=160, unique=True)
    competition = models.ForeignKey(Competition, on_delete=models.PROTECT, related_name="seasons")
    label = models.CharField(max_length=40)
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-start_year", "label"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_year__gte=models.F("start_year")), name="season_years_are_ordered"),
        ]

    def __str__(self) -> str:
        return f"{self.competition.name} {self.label}"


class Team(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=160, unique=True)
    name = models.CharField(max_length=160)
    country_code = models.CharField(max_length=3, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    source_license = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Player(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=160, unique=True)
    name = models.CharField(max_length=160)
    birth_date = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    source_license = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PlayerCareerEntry(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=160, unique=True)
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="career_entries")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="career_entries")
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    transfer_type = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["player", "start_year"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_year__isnull=True) | models.Q(end_year__gte=models.F("start_year")),
                name="career_years_are_ordered",
            ),
        ]


class FootballMatch(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=160, unique=True)
    competition = models.ForeignKey(Competition, on_delete=models.PROTECT, related_name="matches")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="matches")
    played_on = models.DateField()
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_matches")
    regulation_home_goals = models.PositiveSmallIntegerField()
    regulation_away_goals = models.PositiveSmallIntegerField()
    final_home_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    final_away_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    went_extra_time = models.BooleanField(default=False)
    went_to_penalties = models.BooleanField(default=False)
    source_url = models.URLField(max_length=500, blank=True)
    source_license = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["-played_on"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(home_team=models.F("away_team")), name="football_match_teams_differ"),
        ]


class MatchLineup(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    football_match = models.ForeignKey(FootballMatch, on_delete=models.CASCADE, related_name="lineups")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="lineups")
    formation = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["football_match", "team"], name="unique_match_lineup_team"),
        ]


class LineupSlot(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lineup = models.ForeignKey(MatchLineup, on_delete=models.CASCADE, related_name="slots")
    position = models.CharField(max_length=24)
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="lineup_slots")
    is_starter = models.BooleanField(default=True)
    slot_order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["slot_order"]
        constraints = [
            models.UniqueConstraint(fields=["lineup", "slot_order"], name="unique_lineup_slot_order"),
        ]


class Question(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.CharField(max_length=24, choices=MODE_CHOICES)
    difficulty = models.CharField(max_length=8, choices=DIFFICULTY_CHOICES, default="medium")
    status = models.CharField(max_length=12, choices=QUESTION_STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_questions"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_questions"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    source_references = models.ManyToManyField(SourceReference, blank=True, related_name="questions")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "mode"])]

    def __str__(self) -> str:
        return f"{self.mode} / {self.id}"

    def validate_publishable(self) -> None:
        missing_languages = {language for language, _ in LANGUAGE_CHOICES} - set(
            self.translations.values_list("language", flat=True)
        )
        if missing_languages:
            raise ValidationError({"translations": f"Eksik çeviri: {', '.join(sorted(missing_languages))}."})
        if not hasattr(self, "payload"):
            raise ValidationError({"payload": "Yayın için soru payload kaydı zorunludur."})
        sources = self.source_references.all()
        if not sources.exists():
            raise ValidationError({"source_references": "Yayın için en az bir kaynak gerekir."})
        if sources.exclude(license_status="verified").exists():
            raise ValidationError({"source_references": "Lisansı doğrulanmamış kaynak yayınlanamaz."})


class QuestionPayload(TimestampedModel):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name="payload")
    public_payload = models.JSONField(default=dict)
    answer_data = models.JSONField(default=dict)


class QuestionTranslation(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    prompt = models.TextField()
    choices = models.JSONField(default=list, blank=True)
    hints = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["language"]
        constraints = [
            models.UniqueConstraint(fields=["question", "language"], name="unique_question_translation_language"),
        ]


class AnswerAlias(TimestampedModel):
    ENTITY_CHOICES = (("player", "Player"), ("team", "Team"), ("term", "Term"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=12, choices=ENTITY_CHOICES)
    entity_external_id = models.CharField(max_length=160)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    alias = models.CharField(max_length=160)
    normalized_alias = models.CharField(max_length=160)
    source_reference = models.ForeignKey(SourceReference, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "entity_external_id", "language", "normalized_alias"],
                name="unique_answer_alias",
            ),
        ]
