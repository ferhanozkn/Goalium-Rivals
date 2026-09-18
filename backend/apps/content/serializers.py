from rest_framework import serializers
from django.db import transaction
from drf_spectacular.utils import extend_schema_field

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


class SourceReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceReference
        fields = ["id", "provider", "url", "license_name", "license_status", "accessed_at", "notes"]
        read_only_fields = ["id", "accessed_at"]


class CompetitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competition
        fields = ["id", "external_id", "name", "country_code", "kind", "source_url", "source_license"]
        read_only_fields = fields


class SeasonSerializer(serializers.ModelSerializer):
    competition_id = serializers.UUIDField(source="competition.id", read_only=True)

    class Meta:
        model = Season
        fields = ["id", "external_id", "competition_id", "label", "start_year", "end_year"]
        read_only_fields = fields


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "external_id", "name", "country_code", "source_url", "source_license"]
        read_only_fields = fields


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ["id", "external_id", "name", "birth_date", "nationality", "source_url", "source_license"]
        read_only_fields = fields


class PlayerCareerEntrySerializer(serializers.ModelSerializer):
    player_id = serializers.UUIDField(source="player.id", read_only=True)
    team_id = serializers.UUIDField(source="team.id", read_only=True)

    class Meta:
        model = PlayerCareerEntry
        fields = ["id", "external_id", "player_id", "team_id", "start_year", "end_year", "transfer_type"]
        read_only_fields = fields


class FootballMatchSerializer(serializers.ModelSerializer):
    competition_id = serializers.UUIDField(source="competition.id", read_only=True)
    season_id = serializers.UUIDField(source="season.id", read_only=True)
    home_team_id = serializers.UUIDField(source="home_team.id", read_only=True)
    away_team_id = serializers.UUIDField(source="away_team.id", read_only=True)

    class Meta:
        model = FootballMatch
        fields = [
            "id",
            "external_id",
            "competition_id",
            "season_id",
            "played_on",
            "home_team_id",
            "away_team_id",
            "regulation_home_goals",
            "regulation_away_goals",
            "final_home_goals",
            "final_away_goals",
            "went_extra_time",
            "went_to_penalties",
            "source_url",
            "source_license",
        ]
        read_only_fields = fields


class MatchLineupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchLineup
        fields = ["id", "football_match_id", "team_id", "formation"]
        read_only_fields = fields


class LineupSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineupSlot
        fields = ["id", "lineup_id", "position", "player_id", "is_starter", "slot_order"]
        read_only_fields = fields


class AnswerAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerAlias
        fields = ["id", "entity_type", "entity_external_id", "language", "alias", "normalized_alias", "source_reference"]
        read_only_fields = ["id"]


class QuestionPayloadEditorSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionPayload
        fields = ["public_payload", "answer_data"]


class QuestionTranslationEditorSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionTranslation
        fields = ["language", "prompt", "choices", "hints"]


class PublicTranslationSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"])
    prompt = serializers.CharField()
    choices = serializers.ListField()
    hints = serializers.ListField()


class QuestionEditorSerializer(serializers.ModelSerializer):
    payload = QuestionPayloadEditorSerializer(required=False, allow_null=True)
    translations = QuestionTranslationEditorSerializer(many=True, required=False)
    source_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)
    source_references = SourceReferenceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "mode",
            "difficulty",
            "status",
            "created_by",
            "approved_by",
            "approved_at",
            "published_at",
            "created_at",
            "updated_at",
            "payload",
            "translations",
            "source_ids",
            "source_references",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "approved_by",
            "approved_at",
            "published_at",
            "created_at",
            "updated_at",
            "source_references",
        ]

    @transaction.atomic
    def create(self, validated_data):
        payload_data = validated_data.pop("payload", None)
        translations_data = validated_data.pop("translations", [])
        source_ids = validated_data.pop("source_ids", [])
        sources = SourceReference.objects.filter(id__in=source_ids)
        if sources.count() != len(set(source_ids)):
            raise serializers.ValidationError({"source_ids": "Bir veya daha fazla kaynak bulunamadı."})
        question = Question.objects.create(**validated_data)
        if payload_data is not None:
            QuestionPayload.objects.create(question=question, **payload_data)
        QuestionTranslation.objects.bulk_create(
            [QuestionTranslation(question=question, **translation) for translation in translations_data]
        )
        if source_ids:
            question.source_references.set(sources)
        return question


class QuestionPublicSerializer(serializers.ModelSerializer):
    translation = serializers.SerializerMethodField()
    payload = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ["id", "mode", "difficulty", "translation", "payload"]
        read_only_fields = fields

    @extend_schema_field(PublicTranslationSerializer)
    def get_translation(self, question):
        language = self.context["language"]
        translation = next((item for item in question.translations.all() if item.language == language), None)
        if translation is None:
            return None
        return {
            "language": translation.language,
            "prompt": translation.prompt,
            "choices": translation.choices,
            "hints": translation.hints,
        }

    @extend_schema_field(serializers.JSONField)
    def get_payload(self, question):
        try:
            return question.payload.public_payload
        except QuestionPayload.DoesNotExist:
            return {}
