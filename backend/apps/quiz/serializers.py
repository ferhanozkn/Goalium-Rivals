from rest_framework import serializers

from apps.quiz.models import GameSession, Match, MatchParticipant


class GameSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameSession
        fields = ["id", "kind", "modes", "language", "status", "started_at", "finished_at", "created_at"]
        read_only_fields = fields


class MatchParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchParticipant
        fields = ["id", "display_name", "score", "connected", "joined_at"]
        read_only_fields = fields


class MatchSerializer(serializers.ModelSerializer):
    participants = MatchParticipantSerializer(many=True, read_only=True)
    game_session_id = serializers.UUIDField(source="game_session.id", read_only=True)
    ranked_eligible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "game_session_id",
            "match_type",
            "origin",
            "is_mixed",
            "language",
            "status",
            "ranked_eligible",
            "participants",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class MatchCreateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"], default="tr")
    is_mixed = serializers.BooleanField(default=True)
    origin = serializers.ChoiceField(choices=["invite", "matchmaking"], default="invite")


class PracticeSessionCreateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"], default="tr")
    modes = serializers.ListField(child=serializers.CharField(max_length=24), allow_empty=False)


class ModeDefinitionSerializer(serializers.Serializer):
    id = serializers.CharField()
    title_key = serializers.CharField()
    description_key = serializers.CharField()
    duration_seconds = serializers.IntegerField()


class PracticeSessionResponseSerializer(serializers.Serializer):
    session = GameSessionSerializer()
    actor_type = serializers.ChoiceField(choices=["guest", "user"])


class MatchJoinResponseSerializer(serializers.Serializer):
    participant_id = serializers.UUIDField()
    match = MatchSerializer()


class MatchJoinRequestSerializer(serializers.Serializer):
    pass
