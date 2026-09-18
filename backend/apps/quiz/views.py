from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema

from apps.accounts.authentication import GuestTokenAuthentication
from apps.quiz.constants import MODE_DEFINITIONS
from apps.quiz.models import GameSession, Match
from apps.quiz.serializers import (
    GameSessionSerializer,
    MatchCreateSerializer,
    MatchJoinResponseSerializer,
    MatchJoinRequestSerializer,
    MatchSerializer,
    ModeDefinitionSerializer,
    PracticeSessionCreateSerializer,
    PracticeSessionResponseSerializer,
)
from apps.quiz.services import create_live_match, join_live_match, request_actor


ACTOR_AUTHENTICATION = [JWTAuthentication, GuestTokenAuthentication]


@extend_schema(responses={200: ModeDefinitionSerializer(many=True)}, tags=["quiz"])
@api_view(["GET"])
@permission_classes([])
def modes(request):
    return Response(MODE_DEFINITIONS)


@extend_schema(request=PracticeSessionCreateSerializer, responses={201: PracticeSessionResponseSerializer}, tags=["quiz"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def practice_sessions(request):
    actor = request_actor(request)
    serializer = PracticeSessionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        session = GameSession.objects.create(
            kind="practice",
            modes=serializer.validated_data["modes"],
            language=serializer.validated_data["language"],
            status="active",
        )
    return Response(
        {
            "session": GameSessionSerializer(session).data,
            "actor_type": "guest" if actor["guest_session"] else "user",
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(request=MatchCreateSerializer, responses={201: MatchSerializer}, tags=["quiz"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def matches(request):
    serializer = MatchCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    match = create_live_match(request_actor(request), **serializer.validated_data)
    return Response(MatchSerializer(match).data, status=status.HTTP_201_CREATED)


@extend_schema(responses={200: MatchSerializer}, tags=["quiz"])
@api_view(["GET"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def match_detail(request, match_id):
    match = Match.objects.prefetch_related("participants").filter(id=match_id).first()
    if match is None:
        return Response({"detail": "Maç bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    return Response(MatchSerializer(match).data)


@extend_schema(request=MatchJoinRequestSerializer, responses={200: MatchJoinResponseSerializer}, tags=["quiz"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def match_join(request, match_id):
    with transaction.atomic():
        match = Match.objects.select_for_update().filter(id=match_id).first()
        if match is None:
            return Response({"detail": "Maç bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
        participant = join_live_match(match, request_actor(request))
    match.refresh_from_db()
    return Response({"participant_id": str(participant.id), "match": MatchSerializer(match).data})
