from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError

from apps.content.models import (
    AnswerAlias,
    Competition,
    FootballMatch,
    LineupSlot,
    MatchLineup,
    Player,
    PlayerCareerEntry,
    Question,
    QuestionPayload,
    QuestionTranslation,
    Season,
    SourceReference,
    Team,
)
from apps.content.services import transition_question


@admin.register(SourceReference)
class SourceReferenceAdmin(admin.ModelAdmin):
    list_display = ("provider", "license_name", "license_status", "accessed_at")
    list_filter = ("license_status", "provider")
    search_fields = ("provider", "url", "license_name")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "difficulty", "status", "approved_by", "published_at")
    list_filter = ("mode", "difficulty", "status")
    search_fields = ("id",)
    readonly_fields = ("status", "approved_by", "approved_at", "published_at", "created_at", "updated_at")
    actions = ("submit_for_review", "approve_questions", "publish_questions", "retire_questions")

    def _transition_selected(self, request, queryset, target_status):
        changed = 0
        for question in queryset:
            try:
                transition_question(question.id, target_status, request.user)
            except (Question.DoesNotExist, ValidationError) as exc:
                self.message_user(request, f"{question.id}: {exc}", level=messages.ERROR)
            else:
                changed += 1
        self.message_user(request, f"{changed} soru {target_status} durumuna taşındı.", level=messages.SUCCESS)

    @admin.action(description="Seçilenleri incelemeye gönder")
    def submit_for_review(self, request, queryset):
        self._transition_selected(request, queryset, "in_review")

    @admin.action(description="Seçilenleri onayla")
    def approve_questions(self, request, queryset):
        self._transition_selected(request, queryset, "approved")

    @admin.action(description="Seçilenleri yayınla")
    def publish_questions(self, request, queryset):
        self._transition_selected(request, queryset, "published")

    @admin.action(description="Seçilenleri yayından kaldır")
    def retire_questions(self, request, queryset):
        self._transition_selected(request, queryset, "retired")


@admin.register(QuestionTranslation)
class QuestionTranslationAdmin(admin.ModelAdmin):
    list_display = ("question", "language", "prompt")
    list_filter = ("language",)
    search_fields = ("prompt",)


@admin.register(QuestionPayload)
class QuestionPayloadAdmin(admin.ModelAdmin):
    list_display = ("question", "updated_at")


@admin.register(AnswerAlias)
class AnswerAliasAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_external_id", "language", "alias")
    list_filter = ("entity_type", "language")
    search_fields = ("entity_external_id", "alias", "normalized_alias")


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "country_code", "external_id")
    list_filter = ("kind", "country_code")
    search_fields = ("name", "external_id")


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("label", "competition", "start_year", "end_year")
    search_fields = ("label", "external_id")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "country_code", "external_id")
    search_fields = ("name", "external_id")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "nationality", "external_id")
    search_fields = ("name", "external_id")


@admin.register(PlayerCareerEntry)
class PlayerCareerEntryAdmin(admin.ModelAdmin):
    list_display = ("player", "team", "start_year", "end_year")
    search_fields = ("player__name", "team__name", "external_id")


@admin.register(FootballMatch)
class FootballMatchAdmin(admin.ModelAdmin):
    list_display = ("played_on", "home_team", "away_team", "competition", "external_id")
    list_filter = ("competition", "went_extra_time", "went_to_penalties")
    search_fields = ("home_team__name", "away_team__name", "external_id")


@admin.register(MatchLineup)
class MatchLineupAdmin(admin.ModelAdmin):
    list_display = ("football_match", "team", "formation")
    search_fields = ("football_match__external_id", "team__name")


@admin.register(LineupSlot)
class LineupSlotAdmin(admin.ModelAdmin):
    list_display = ("lineup", "slot_order", "position", "player", "is_starter")
    list_filter = ("is_starter", "position")
