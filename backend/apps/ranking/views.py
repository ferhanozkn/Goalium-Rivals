from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from apps.quiz.serializers import MatchSerializer
from apps.quiz.engine.practice import round_public_state
from apps.ranking.engine import dequeue_matchmaking, enqueue_matchmaking, leaderboard, matchmaking_status, user_stats
from apps.ranking.serializers import (
    LeaderboardResponseSerializer,
    MatchmakingQueueSerializer,
    MatchmakingResponseSerializer,
    RatingStatsSerializer,
)


def _queue_response(result):
    response = {
        "status": result["status"],
        "queue": result["queue"],
        "position": result.get("position"),
    }
    if result["status"] == "matched":
        state = result["participant"].round_states.select_related("round", "round__question").filter(status="active").order_by("round__order").first()
        response.update(
            {
                "match": MatchSerializer(result["match"]).data,
                "participant_id": result["participant"].id,
                "round": round_public_state(state.round, private_state=state.private_state, deadline=state.deadline) if state else None,
            }
        )
    return response


@extend_schema_view(
    post=extend_schema(request=MatchmakingQueueSerializer, responses={200: MatchmakingResponseSerializer}, tags=["matchmaking"]),
    delete=extend_schema(
        parameters=[OpenApiParameter(name="language", type=str, enum=["tr", "en"], required=False)],
        responses={204: None},
        tags=["matchmaking"],
    ),
)
@api_view(["POST", "DELETE"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def queue(request):
    if request.method == "DELETE":
        serializer = MatchmakingQueueSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        dequeue_matchmaking(request.user, **serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = MatchmakingQueueSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = enqueue_matchmaking(request.user, **serializer.validated_data)
    return Response(_queue_response(result), status=status.HTTP_200_OK)


@extend_schema(
    parameters=[OpenApiParameter(name="language", type=str, enum=["tr", "en"], required=False)],
    responses={200: MatchmakingResponseSerializer},
    tags=["matchmaking"],
)
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def queue_status(request):
    return Response(_queue_response(matchmaking_status(request.user, language=request.query_params.get("language", "tr"))))


@extend_schema(
    parameters=[
        OpenApiParameter(name="period", type=str, enum=["global", "season"], required=False),
        OpenApiParameter(name="season", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
    ],
    responses={200: LeaderboardResponseSerializer},
    tags=["ranking"],
)
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def leaderboard_view(request):
    period = request.query_params.get("period", "global")
    if period not in {"global", "season"}:
        return Response({"detail": "period global veya season olmalıdır."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
    except ValueError:
        return Response({"detail": "limit sayı olmalıdır."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(leaderboard(period=period, season=request.query_params.get("season"), limit=limit))


@extend_schema(responses={200: RatingStatsSerializer}, tags=["ranking"])
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def me_stats(request):
    return Response(user_stats(request.user))
