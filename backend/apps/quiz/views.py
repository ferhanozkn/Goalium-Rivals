from django.db import transaction
from django.core.exceptions import ValidationError
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
    PracticeAnswerResponseSerializer,
    PracticeSessionAnswerSerializer,
    PracticeSessionCreateSerializer,
    PracticeSessionDetailSerializer,
    PracticeSessionResponseSerializer,
)
from apps.quiz.engine import create_practice_session, get_practice_participant, submit_practice_answer
from apps.quiz.engine.practice import PracticeRoundConflict, round_public_state
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
    try:
        session, _, participant, round_instance = create_practice_session(
            actor,
            serializer.validated_data["modes"],
            serializer.validated_data["language"],
        )
    except ValidationError as exc:
        return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "session": GameSessionSerializer(session).data,
            "actor_type": "guest" if actor["guest_session"] else "user",
            "participant_id": participant.id,
            "round": round_public_state(round_instance),
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(responses={200: PracticeSessionDetailSerializer}, tags=["quiz"])
@api_view(["GET"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def practice_session_detail(request, session_id):
    actor = request_actor(request)
    try:
        participant = get_practice_participant(session_id, actor)
    except ValidationError as exc:
        return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_404_NOT_FOUND)
    session = participant.match.game_session
    round_instance = participant.match.rounds.filter(status="active").order_by("order").first()
    return Response(
        {
            "session": GameSessionSerializer(session).data,
            "participant_id": participant.id,
            "round": round_public_state(round_instance) if round_instance else None,
        }
    )


@extend_schema(
    request=PracticeSessionAnswerSerializer,
    responses={200: PracticeAnswerResponseSerializer},
    tags=["quiz"],
)
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def practice_answers(request, session_id):
    actor = request_actor(request)
    serializer = PracticeSessionAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        participant = get_practice_participant(session_id, actor)
        round_instance, participant, next_round = submit_practice_answer(
            session_id,
            participant.id,
            serializer.validated_data["round_id"],
            serializer.validated_data["answer"],
        )
    except (ValidationError, PracticeRoundConflict) as exc:
        return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    final_answer = round_instance.answers.filter(participant=participant).first()
    result = final_answer.result if final_answer else "active"
    points = final_answer.points if final_answer else 0
    return Response(
        {
            "round": round_public_state(round_instance),
            "result": result,
            "points": points,
            "score": participant.score,
            "next_round": round_public_state(next_round) if next_round else None,
        }
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
