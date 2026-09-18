from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.quiz.models import GameSession, Match, MatchParticipant


def request_actor(request):
    if getattr(request.user, "is_authenticated", False) and not hasattr(request, "guest_session"):
        return {"user": request.user, "guest_session": None, "display_name": request.user.display_name}
    guest_session = getattr(request, "guest_session", None)
    if guest_session:
        return {"user": None, "guest_session": guest_session, "display_name": guest_session.display_name or "Guest"}
    raise PermissionDenied("Aktif bir kullanıcı veya misafir oturumu gerekir.")


@transaction.atomic
def create_live_match(actor, *, language: str = "tr", is_mixed: bool = True, origin: str = "invite"):
    game_session = GameSession.objects.create(kind="live_1v1", modes=[], language=language, status="waiting")
    match = Match.objects.create(
        game_session=game_session,
        match_type="live_1v1",
        origin=origin,
        is_mixed=is_mixed,
        language=language,
    )
    MatchParticipant.objects.create(
        match=match,
        user=actor["user"],
        guest_session=actor["guest_session"],
        display_name=actor["display_name"],
    )
    return match


@transaction.atomic
def join_live_match(match: Match, actor):
    if match.match_type != "live_1v1":
        raise PermissionDenied("Bu maç canlı 1v1 değil.")
    participant_filter = {"match": match}
    if actor["user"]:
        participant_filter["user"] = actor["user"]
    else:
        participant_filter["guest_session"] = actor["guest_session"]
    participant = MatchParticipant.objects.filter(**participant_filter).first()
    if participant is None:
        if match.participants.count() >= match.max_players:
            raise PermissionDenied("Maç katılımcı sınırına ulaştı.")
        participant = MatchParticipant.objects.create(
            match=match,
            user=actor["user"],
            guest_session=actor["guest_session"],
            display_name=actor["display_name"],
        )
    if match.participants.count() >= 2 and match.status == "waiting":
        match.status = "live"
        match.started_at = timezone.now()
        match.game_session.status = "active"
        match.game_session.started_at = match.started_at
        match.game_session.save(update_fields=["status", "started_at"])
        match.save(update_fields=["status", "started_at"])
    return participant
