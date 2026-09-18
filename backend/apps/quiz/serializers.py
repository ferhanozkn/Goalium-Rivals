from rest_framework import serializers

from apps.quiz.models import GameSession, Match, MatchParticipant


class GameSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameSession
        fields = ["id", "kind", "modes", "language", "status", "started_at", "finished_at", "deadline", "created_at"]
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
            "max_players",
            "room_code",
            "settings",
            "result",
            "participants",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class MatchCreateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"], default="tr")
    is_mixed = serializers.BooleanField(default=True)
    origin = serializers.ChoiceField(choices=["invite"], default="invite")


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
    participant_id = serializers.UUIDField()
    round = serializers.JSONField()


class PracticeSessionDetailSerializer(serializers.Serializer):
    session = GameSessionSerializer()
    participant_id = serializers.UUIDField()
    round = serializers.JSONField(allow_null=True)


class PracticeSessionAnswerSerializer(serializers.Serializer):
    round_id = serializers.UUIDField()
    answer = serializers.JSONField()


class PracticeAnswerResponseSerializer(serializers.Serializer):
    round = serializers.JSONField()
    result = serializers.ChoiceField(choices=["correct", "wrong", "timeout", "skipped", "active"])
    points = serializers.IntegerField()
    score = serializers.IntegerField()
    next_round = serializers.JSONField(allow_null=True)


class MatchJoinResponseSerializer(serializers.Serializer):
    participant_id = serializers.UUIDField()
    match = MatchSerializer()


class MatchJoinRequestSerializer(serializers.Serializer):
    pass


class DuelCreateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"], default="tr")
    modes = serializers.ListField(child=serializers.ChoiceField(choices=["hangman", "career_path", "timed_trivia", "historical_score", "missing_lineup"]), allow_empty=False, required=False)


class MultiplayerAnswerSerializer(serializers.Serializer):
    round_id = serializers.UUIDField()
    answer = serializers.JSONField()


class RoomCreateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"], default="tr")
    is_mixed = serializers.BooleanField(default=True)
    mode = serializers.ChoiceField(choices=["hangman", "career_path", "timed_trivia", "historical_score", "missing_lineup"], required=False, allow_null=True)
    round_count = serializers.IntegerField(min_value=1, max_value=5, default=5)
    duration_multiplier = serializers.FloatField(min_value=0.5, max_value=2.0, default=1.0)

    def validate(self, attrs):
        if not attrs.get("is_mixed") and not attrs.get("mode"):
            raise serializers.ValidationError({"mode": "Tek modlu oda için mod seçilmelidir."})
        return attrs


class RoomJoinSerializer(serializers.Serializer):
    pass


class RoomResponseSerializer(serializers.Serializer):
    match = MatchSerializer()
    participant_id = serializers.UUIDField()
    round = serializers.JSONField(allow_null=True)
    actor_type = serializers.ChoiceField(choices=["guest", "user"])
    expires_at = serializers.DateTimeField(allow_null=True)


class DuelResponseSerializer(serializers.Serializer):
    match = MatchSerializer()
    participant_id = serializers.UUIDField()
    round = serializers.JSONField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)


class MultiplayerAnswerResponseSerializer(serializers.Serializer):
    phase = serializers.ChoiceField(choices=["progress", "waiting", "advanced", "finished"])
    result = serializers.ChoiceField(choices=["correct", "wrong", "timeout", "skipped", "active"])
    points = serializers.IntegerField()
    score = serializers.IntegerField()
    round = serializers.JSONField()
    next_round = serializers.JSONField(allow_null=True)
    match = serializers.JSONField()
