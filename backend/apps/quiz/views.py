from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
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
    DuelCreateSerializer,
    DuelResponseSerializer,
    MultiplayerAnswerSerializer,
    MultiplayerAnswerResponseSerializer,
    RoomCreateSerializer,
    RoomJoinSerializer,
    RoomResponseSerializer,
)
from apps.quiz.engine import (
    create_duel,
    create_practice_session,
    create_room,
    expire_duel,
    get_practice_participant,
    join_duel,
    join_room,
    participant_for_match,
    start_room,
    submit_multiplayer_answer,
    submit_practice_answer,
)
from apps.quiz.engine.practice import PracticeRoundConflict, round_public_state
from apps.quiz.engine.multiplayer import MultiplayerConflict
from apps.quiz.services import create_live_match, join_live_match, request_actor


ACTOR_AUTHENTICATION = [JWTAuthentication, GuestTokenAuthentication]


def _user_only(request):
    if hasattr(request, "guest_session") or not getattr(request.user, "is_authenticated", False):
        raise PermissionDenied("Bu işlem hesaplı kullanıcı gerektirir.")
    return request.user


def _multiplayer_response(match, participant, actor_type):
    match.refresh_from_db()
    state = participant.round_states.select_related("round", "round__question").filter(status="active").order_by("round__order").first()
    return {
        "match": MatchSerializer(match).data,
        "participant_id": participant.id,
        "round": round_public_state(state.round, private_state=state.private_state, deadline=state.deadline) if state else None,
        "actor_type": actor_type,
        "expires_at": match.game_session.deadline,
    }


def _multiplayer_error(exc, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"detail": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
        status=status_code,
    )


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


@extend_schema(request=DuelCreateSerializer, responses={201: DuelResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def duels(request):
    user = _user_only(request)
    serializer = DuelCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        match, participant = create_duel(user, **serializer.validated_data)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    return Response(_multiplayer_response(match, participant, "user"), status=status.HTTP_201_CREATED)


@extend_schema(responses={200: DuelResponseSerializer}, tags=["multiplayer"])
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def duel_detail(request, duel_id):
    user = _user_only(request)
    try:
        match = expire_duel(duel_id)
    except Match.DoesNotExist:
        return Response({"detail": "Düello bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    participant = participant_for_match(match, user=user)
    if participant is None:
        return Response({"detail": "Bu düelloya erişim izniniz yok."}, status=status.HTTP_403_FORBIDDEN)
    return Response(_multiplayer_response(match, participant, "user"))


@extend_schema(request=RoomJoinSerializer, responses={200: DuelResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def duel_join(request, duel_id):
    user = _user_only(request)
    try:
        match, participant = join_duel(duel_id, user)
    except Match.DoesNotExist:
        return Response({"detail": "Düello bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    return Response(_multiplayer_response(match, participant, "user"))


@extend_schema(request=MultiplayerAnswerSerializer, responses={200: MultiplayerAnswerResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def duel_play(request, duel_id):
    user = _user_only(request)
    serializer = MultiplayerAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    match = Match.objects.filter(id=duel_id, match_type="async_duel").first()
    if match is None:
        return Response({"detail": "Düello bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    participant = participant_for_match(match, user=user)
    if participant is None:
        return Response({"detail": "Bu düelloya erişim izniniz yok."}, status=status.HTTP_403_FORBIDDEN)
    try:
        result = submit_multiplayer_answer(duel_id, participant.id, **serializer.validated_data)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    return Response(result)


@extend_schema(request=RoomCreateSerializer, responses={201: RoomResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def rooms(request):
    actor = request_actor(request)
    serializer = RoomCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        match = create_room(actor, **serializer.validated_data)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    participant = match.participants.get(**({"user": actor["user"]} if actor["user"] else {"guest_session": actor["guest_session"]}))
    return Response(_multiplayer_response(match, participant, "guest" if actor["guest_session"] else "user"), status=status.HTTP_201_CREATED)


@extend_schema(responses={200: RoomResponseSerializer}, tags=["multiplayer"])
@api_view(["GET"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def room_detail(request, room_code):
    actor = request_actor(request)
    match = Match.objects.filter(room_code=room_code.upper(), match_type="room").first()
    if match is None:
        return Response({"detail": "Oda bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    participant = participant_for_match(match, actor=actor)
    if participant is None:
        return Response({"detail": "Bu odaya erişim izniniz yok."}, status=status.HTTP_403_FORBIDDEN)
    return Response(_multiplayer_response(match, participant, "guest" if actor["guest_session"] else "user"))


@extend_schema(request=RoomJoinSerializer, responses={200: RoomResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def room_join(request, room_code):
    actor = request_actor(request)
    try:
        match, participant = join_room(room_code, actor)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    return Response(_multiplayer_response(match, participant, "guest" if actor["guest_session"] else "user"))


@extend_schema(request=RoomJoinSerializer, responses={200: RoomResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def room_start(request, room_code):
    actor = request_actor(request)
    try:
        match = start_room(room_code, actor)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    participant = participant_for_match(match, actor=actor)
    return Response(_multiplayer_response(match, participant, "guest" if actor["guest_session"] else "user"))


@extend_schema(request=MultiplayerAnswerSerializer, responses={200: MultiplayerAnswerResponseSerializer}, tags=["multiplayer"])
@api_view(["POST"])
@authentication_classes(ACTOR_AUTHENTICATION)
@permission_classes([IsAuthenticated])
def room_answers(request, room_code):
    actor = request_actor(request)
    serializer = MultiplayerAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    match = Match.objects.filter(room_code=room_code.upper(), match_type="room").first()
    if match is None:
        return Response({"detail": "Oda bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    participant = participant_for_match(match, actor=actor)
    if participant is None:
        return Response({"detail": "Bu odaya erişim izniniz yok."}, status=status.HTTP_403_FORBIDDEN)
    try:
        result = submit_multiplayer_answer(match.id, participant.id, **serializer.validated_data)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    return Response(result)


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


@extend_schema(request=MultiplayerAnswerSerializer, responses={200: MultiplayerAnswerResponseSerializer}, tags=["matchmaking"])
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def match_answers(request, match_id):
    user = _user_only(request)
    serializer = MultiplayerAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    match = Match.objects.filter(id=match_id, match_type="live_1v1").first()
    if match is None:
        return Response({"detail": "Maç bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    participant = participant_for_match(match, user=user)
    if participant is None:
        return Response({"detail": "Bu maça erişim izniniz yok."}, status=status.HTTP_403_FORBIDDEN)
    try:
        result = submit_multiplayer_answer(match_id, participant.id, **serializer.validated_data)
    except (ValidationError, MultiplayerConflict) as exc:
        return _multiplayer_error(exc)
    return Response(result)
