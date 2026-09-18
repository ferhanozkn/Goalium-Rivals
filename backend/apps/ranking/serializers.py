from rest_framework import serializers


class MatchmakingQueueSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["tr", "en"], default="tr")


class MatchmakingResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["idle", "queued", "matched"])
    queue = serializers.CharField()
    position = serializers.IntegerField(allow_null=True, required=False)
    match = serializers.JSONField(required=False)
    participant_id = serializers.UUIDField(required=False)
    round = serializers.JSONField(allow_null=True, required=False)


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    user_id = serializers.UUIDField()
    display_name = serializers.CharField()
    rating = serializers.IntegerField()
    matches_played = serializers.IntegerField()
    wins = serializers.IntegerField()
    draws = serializers.IntegerField()
    losses = serializers.IntegerField()
    in_placement = serializers.BooleanField()


class LeaderboardResponseSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=["global", "season"])
    season = serializers.CharField(allow_null=True)
    entries = LeaderboardEntrySerializer(many=True)


class RatingStatsSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    display_name = serializers.CharField()
    rating = serializers.IntegerField()
    matches_played = serializers.IntegerField()
    wins = serializers.IntegerField()
    draws = serializers.IntegerField()
    losses = serializers.IntegerField()
    in_placement = serializers.BooleanField()
    global_rank = serializers.IntegerField(allow_null=True)
    season_rank = serializers.IntegerField(allow_null=True)
