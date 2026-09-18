import json
import math
import secrets
import string
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.quiz.engine.constants import MODE_RULES, mode_duration
from apps.quiz.engine.normalization import normalize_answer
from apps.quiz.engine.practice import _evaluate_round, round_public_state
from apps.quiz.engine.selection import create_round
from apps.quiz.models import Answer, GameSession, Match, MatchParticipant, ParticipantRoundState, Round


MULTIPLAYER_MODES = tuple(MODE_RULES.keys())
ASYNC_WINDOW_HOURS = 48
ROOM_MIN_PLAYERS = 2
ROOM_MAX_PLAYERS = 8
DEFAULT_ROOM_ROUNDS = 5
DEFAULT_DURATION_MULTIPLIER = 1.0


class MultiplayerConflict(ValidationError):
    pass


def _room_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _duration_seconds(mode: str, multiplier: float) -> int:
    return max(1, math.ceil(mode_duration(mode) * multiplier))


def _actor_filter(actor):
    if actor["user"] is not None:
        return {"user": actor["user"]}
    return {"guest_session": actor["guest_session"]}


def _settings_modes(settings: dict) -> list[str]:
    modes = settings.get("modes") or list(MULTIPLAYER_MODES)
    invalid = sorted(set(modes) - set(MULTIPLAYER_MODES))
    if invalid:
        raise ValidationError({"modes": f"Desteklenmeyen oyun modları: {', '.join(invalid)}."})
    return modes


def _fixed_modes(settings: dict) -> list[str]:
    modes = _settings_modes(settings)
    if settings.get("is_mixed", False):
        return list(modes)
    return [modes[0]] * int(settings.get("round_count", 1))


def _create_fixed_rounds(match: Match) -> list[Round]:
    session = match.game_session
    settings = match.settings or {}
    modes = _fixed_modes(settings)
    multiplier = float(settings.get("duration_multiplier", DEFAULT_DURATION_MULTIPLIER))
    rounds = []
    for order, mode in enumerate(modes):
        deadline = timezone.now() + timedelta(seconds=_duration_seconds(mode, multiplier))
        rounds.append(
            create_round(
                session,
                match,
                mode,
                order,
                deadline=deadline,
                status="active" if order == 0 else "pending",
                allow_reuse=True,
                update_session_deadline=False,
            )
        )
    return rounds


def _state_deadline(match: Match, round_instance: Round, started_at=None):
    started_at = started_at or timezone.now()
    multiplier = float((match.settings or {}).get("duration_multiplier", DEFAULT_DURATION_MULTIPLIER))
    return started_at + timedelta(seconds=_duration_seconds(round_instance.mode, multiplier))


def _activate_round_for_participant(participant: MatchParticipant, round_instance: Round, started_at=None):
    return ParticipantRoundState.objects.create(
        participant=participant,
        round=round_instance,
        deadline=_state_deadline(participant.match, round_instance, started_at),
        private_state={},
        status="active",
    )


def _activate_first_round(match: Match):
    first_round = match.rounds.order_by("order").first()
    if first_round is None:
        raise ValidationError({"match": "Maç için soru seti oluşturulamadı."})
    now = timezone.now()
    first_round.status = "active"
    first_round.save(update_fields=["status"])
    for participant in match.participants.all():
        _activate_round_for_participant(participant, first_round, now)
    return first_round


def _start_match_locked(match: Match):
    if match.status not in {"waiting", "live"}:
        raise MultiplayerConflict({"match": "Bu maç başlatılamaz."})
    if match.participants.count() < ROOM_MIN_PLAYERS and match.match_type in {"room", "live_1v1"}:
        raise MultiplayerConflict({"match": "Maçı başlatmak için en az iki oyuncu gerekir."})
    if not match.rounds.exists():
        _create_fixed_rounds(match)
    first_round = match.rounds.order_by("order").first()
    if not match.participants.filter(round_states__round=first_round).exists():
        _activate_first_round(match)
    now = timezone.now()
    match.status = "live"
    match.started_at = match.started_at or now
    match.game_session.status = "active"
    match.game_session.started_at = match.game_session.started_at or now
    match.game_session.save(update_fields=["status", "started_at"])
    match.save(update_fields=["status", "started_at"])
    return match


@transaction.atomic
def start_live_match(match: Match):
    match = Match.objects.select_for_update().select_related("game_session").get(id=match.id)
    if not match.settings:
        match.settings = {
            "is_mixed": match.is_mixed,
            "modes": list(MULTIPLAYER_MODES),
            "round_count": len(MULTIPLAYER_MODES),
            "duration_multiplier": DEFAULT_DURATION_MULTIPLIER,
        }
        match.save(update_fields=["settings"])
    return _start_match_locked(match)


@transaction.atomic
def create_room(actor, *, language="tr", is_mixed=True, mode=None, round_count=DEFAULT_ROOM_ROUNDS, duration_multiplier=DEFAULT_DURATION_MULTIPLIER):
    if not is_mixed and not mode:
        raise ValidationError({"mode": "Tek modlu oda için mod seçilmelidir."})
    modes = list(MULTIPLAYER_MODES) if is_mixed else [mode]
    if round_count < 1 or round_count > len(MULTIPLAYER_MODES):
        raise ValidationError({"round_count": f"Tur sayısı 1 ile {len(MULTIPLAYER_MODES)} arasında olmalıdır."})
    if not is_mixed:
        modes = [mode]
    session = GameSession.objects.create(kind="room", modes=modes, language=language, status="waiting")
    match = Match.objects.create(
        game_session=session,
        match_type="room",
        origin="room",
        is_mixed=is_mixed,
        language=language,
        status="waiting",
        max_players=ROOM_MAX_PLAYERS,
        room_code=_room_code(),
        settings={
            "is_mixed": is_mixed,
            "modes": modes,
            "round_count": len(MULTIPLAYER_MODES) if is_mixed else round_count,
            "duration_multiplier": float(duration_multiplier),
        },
    )
    MatchParticipant.objects.create(
        match=match,
        user=actor["user"],
        guest_session=actor["guest_session"],
        display_name=actor["display_name"],
    )
    return match


@transaction.atomic
def join_room(room_code: str, actor):
    match = Match.objects.select_for_update().filter(room_code=room_code.upper(), match_type="room").first()
    if match is None:
        raise ValidationError({"room": "Oda bulunamadı."})
    if match.status != "waiting":
        raise MultiplayerConflict({"room": "Bu oda artık katılıma açık değil."})
    participant = match.participants.filter(**_actor_filter(actor)).first()
    if participant is None:
        if match.participants.count() >= match.max_players:
            raise MultiplayerConflict({"room": "Oda kapasitesi dolu."})
        participant = MatchParticipant.objects.create(
            match=match,
            user=actor["user"],
            guest_session=actor["guest_session"],
            display_name=actor["display_name"],
        )
    return match, participant


@transaction.atomic
def start_room(room_code: str, actor):
    match = Match.objects.select_for_update().select_related("game_session").filter(room_code=room_code.upper(), match_type="room").first()
    if match is None:
        raise ValidationError({"room": "Oda bulunamadı."})
    owner = match.participants.order_by("joined_at").first()
    if owner is None or not match.participants.filter(id=owner.id, **_actor_filter(actor)).exists():
        raise MultiplayerConflict({"room": "Yalnızca oda sahibi başlatabilir."})
    return _start_match_locked(match)


@transaction.atomic
def create_duel(user, *, language="tr", modes=None):
    modes = modes or list(MULTIPLAYER_MODES)
    invalid = sorted(set(modes) - set(MULTIPLAYER_MODES))
    if not modes or invalid:
        raise ValidationError({"modes": "Asenkron düello için geçerli bir mod seti gerekir."})
    now = timezone.now()
    session = GameSession.objects.create(
        kind="async_duel",
        modes=modes,
        language=language,
        status="active",
        started_at=now,
        deadline=now + timedelta(hours=ASYNC_WINDOW_HOURS),
    )
    match = Match.objects.create(
        game_session=session,
        match_type="async_duel",
        origin="invite",
        is_mixed=len(modes) > 1,
        language=language,
        status="live",
        max_players=2,
        settings={"modes": modes, "is_mixed": len(modes) > 1, "round_count": len(modes), "async": True},
    )
    participant = MatchParticipant.objects.create(match=match, user=user, display_name=user.display_name)
    _create_fixed_rounds(match)
    _activate_first_round(match)
    return match, participant


@transaction.atomic
def join_duel(match_id, user):
    match = Match.objects.select_for_update().select_related("game_session").filter(id=match_id, match_type="async_duel").first()
    if match is None:
        raise ValidationError({"duel": "Düello bulunamadı."})
    _expire_duel_locked(match)
    if match.status != "live":
        raise MultiplayerConflict({"duel": "Bu düello artık katılıma açık değil."})
    if match.participants.filter(user=user).exists():
        raise MultiplayerConflict({"duel": "Bu düelloda zaten varsınız."})
    if match.participants.count() >= match.max_players:
        raise MultiplayerConflict({"duel": "Düello rakip kapasitesine ulaştı."})
    participant = MatchParticipant.objects.create(match=match, user=user, display_name=user.display_name)
    first_round = match.rounds.order_by("order").first()
    _activate_round_for_participant(participant, first_round)
    return match, participant


def _expire_duel_locked(match: Match):
    if match.match_type != "async_duel" or match.status not in {"live", "waiting"}:
        return False
    if match.game_session.deadline is None or timezone.now() < match.game_session.deadline:
        return False
    participants = list(match.participants.order_by("joined_at"))
    match.status = "forfeit"
    match.game_session.status = "expired"
    match.game_session.finished_at = timezone.now()
    match.result = {"reason": "async_window_expired", "winner_participant_id": str(participants[0].id) if participants else None}
    match.game_session.save(update_fields=["status", "finished_at"])
    match.save(update_fields=["status", "result"])
    return True


@transaction.atomic
def expire_duel(match_id):
    match = Match.objects.select_for_update().select_related("game_session").get(id=match_id, match_type="async_duel")
    _expire_duel_locked(match)
    return match


def participant_for_match(match, user=None, actor=None):
    if actor is not None:
        return match.participants.filter(**_actor_filter(actor)).first()
    return match.participants.filter(user=user).first()


def _current_state(participant):
    return (
        participant.round_states.select_related("round", "round__question", "participant__match")
        .filter(status="active")
        .order_by("round__order")
        .first()
    )


def participant_snapshot(participant):
    current = _current_state(participant)
    return {
        "id": str(participant.id),
        "display_name": participant.display_name,
        "score": participant.score,
        "connected": participant.connected,
        "completed": current is None and participant.round_states.exists(),
    }


def match_snapshot(match, participant=None):
    current = _current_state(participant) if participant else None
    return {
        "id": str(match.id),
        "game_session_id": str(match.game_session_id),
        "match_type": match.match_type,
        "origin": match.origin,
        "is_mixed": match.is_mixed,
        "language": match.language,
        "status": match.status,
        "room_code": match.room_code,
        "max_players": match.max_players,
        "settings": match.settings,
        "result": match.result,
        "participants": [participant_snapshot(item) for item in match.participants.all()],
        "current_round": round_public_state(current.round, private_state=current.private_state, deadline=current.deadline) if current else None,
    }


def _finish_match(match, now):
    participants = list(match.participants.order_by("joined_at"))
    score_values = [participant.score for participant in participants]
    high_score = max(score_values) if score_values else 0
    winners = [participant for participant in participants if participant.score == high_score]
    if len(winners) > 1 and not (match.settings or {}).get("sudden_death"):
        response_totals = {
            participant.id: Answer.objects.filter(participant=participant).aggregate(total=Sum("response_ms"))["total"] or 0
            for participant in winners
        }
        fastest = min(response_totals.values())
        fastest_winners = [participant for participant in winners if response_totals[participant.id] == fastest]
        if len(fastest_winners) == 1:
            winners = fastest_winners
    match.status = "finished"
    match.finished_at = now
    match.result = {
        "winner_participant_id": str(winners[0].id) if len(winners) == 1 else None,
        "draw": len(winners) != 1,
        "scores": {str(participant.id): participant.score for participant in participants},
    }
    match.game_session.status = "finished"
    match.game_session.finished_at = now
    match.game_session.save(update_fields=["status", "finished_at"])
    match.save(update_fields=["status", "finished_at", "result"])
    from apps.ranking.engine import apply_rating_for_match

    apply_rating_for_match(match)


def _needs_sudden_death(match):
    if match.match_type != "live_1v1" or (match.settings or {}).get("sudden_death"):
        return False
    participants = list(match.participants.order_by("joined_at"))
    if len(participants) != 2 or participants[0].score != participants[1].score:
        return False
    response_totals = {
        participant.id: Answer.objects.filter(participant=participant).aggregate(total=Sum("response_ms"))["total"] or 0
        for participant in participants
    }
    return response_totals[participants[0].id] == response_totals[participants[1].id]


def _start_sudden_death(match, now):
    mode = match.rounds.order_by("order").values_list("mode", flat=True).first() or "timed_trivia"
    settings = {**(match.settings or {}), "sudden_death": True}
    match.settings = settings
    match.save(update_fields=["settings"])
    round_instance = create_round(
        match.game_session,
        match,
        mode,
        match.rounds.count(),
        deadline=now + timedelta(seconds=_duration_seconds(mode, float(settings.get("duration_multiplier", DEFAULT_DURATION_MULTIPLIER)))),
        status="active",
        allow_reuse=True,
        update_session_deadline=False,
    )
    for participant in match.participants.all():
        _activate_round_for_participant(participant, round_instance, now)
    return round_instance


def _all_states_finished(match, round_instance):
    participant_ids = list(match.participants.values_list("id", flat=True))
    return not ParticipantRoundState.objects.filter(
        participant_id__in=participant_ids, round=round_instance, status="active"
    ).exists() and len(participant_ids) > 0


def _advance_live_match(match, round_instance, now):
    if not _all_states_finished(match, round_instance):
        return None
    round_instance.status = "timeout" if round_instance.participant_states.filter(status="timeout").exists() else "finished"
    round_instance.save(update_fields=["status"])
    next_round = match.rounds.filter(order__gt=round_instance.order).order_by("order").first()
    if next_round is None:
        if _needs_sudden_death(match):
            return _start_sudden_death(match, now)
        _finish_match(match, now)
        return None
    next_round.status = "active"
    next_round.save(update_fields=["status"])
    for participant in match.participants.all():
        _activate_round_for_participant(participant, next_round, now)
    return next_round


def _advance_async_match(match, participant, round_instance, now):
    next_round = match.rounds.filter(order__gt=round_instance.order).order_by("order").first()
    if next_round is None:
        others_done = match.participants.exclude(id=participant.id).exclude(
            round_states__status="active"
        ).count() == match.participants.exclude(id=participant.id).count()
        if match.participants.count() > 1 and others_done:
            _finish_match(match, now)
        return None
    _activate_round_for_participant(participant, next_round, now)
    return next_round


def _finish_answer(state, participant, answer, result, points, now):
    from apps.quiz.models import Answer

    Answer.objects.create(
        round=state.round,
        participant=participant,
        raw_answer=answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False, sort_keys=True),
        normalized_answer=normalize_answer(answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False, sort_keys=True), state.round.match.language),
        result=result,
        response_ms=max(0, int((now - state.started_at).total_seconds() * 1000)),
        points=points,
    )
    state.status = "timeout" if result == "timeout" else "finished"
    state.finished_at = now
    state.save(update_fields=["status", "finished_at", "private_state"])
    MatchParticipant.objects.filter(id=participant.id).update(score=F("score") + points)
    participant.refresh_from_db()


@transaction.atomic
def submit_multiplayer_answer(match_id, participant_id, round_id, answer):
    match = Match.objects.select_for_update().select_related("game_session").get(id=match_id)
    participant = match.participants.select_for_update().get(id=participant_id)
    state = (
        ParticipantRoundState.objects.select_for_update()
        .select_related("round", "round__question", "round__match")
        .select_for_update(of=("self",))
        .get(participant=participant, round_id=round_id)
    )
    if match.status not in {"live"}:
        raise MultiplayerConflict({"match": "Bu maç artık aktif değil."})
    if state.status != "active":
        raise MultiplayerConflict({"round": "Bu tur artık aktif değil."})
    now = timezone.now()
    if match.match_type == "async_duel" and match.game_session.deadline and now >= match.game_session.deadline:
        _expire_duel_locked(match)
        raise MultiplayerConflict({"duel": "Düello süresi doldu."})
    if now >= state.deadline:
        result, points, private_state = "timeout", 0, state.private_state
    else:
        result, points, private_state = _evaluate_round(
            state.round, answer, now, private_state=state.private_state, deadline=state.deadline
        )
    state.private_state = private_state
    if result is None:
        state.save(update_fields=["private_state"])
        return {
            "phase": "progress",
            "result": "active",
            "points": 0,
            "score": participant.score,
            "round": round_public_state(state.round, private_state=state.private_state, deadline=state.deadline),
            "next_round": None,
            "match": match_snapshot(match, participant),
        }
    _finish_answer(state, participant, answer, result, points, now)
    if match.match_type in {"room", "live_1v1"}:
        next_round = _advance_live_match(match, state.round, now)
        waiting = next_round is None and match.status == "live"
    else:
        next_round = _advance_async_match(match, participant, state.round, now)
        waiting = False
    match.refresh_from_db()
    next_state = participant.round_states.select_related("round", "round__question").filter(status="active").order_by("round__order").first()
    participant_waiting = match.match_type == "async_duel" and next_state is None and match.status == "live"
    return {
        "phase": "waiting" if waiting or participant_waiting else ("finished" if match.status != "live" else "advanced"),
        "result": result,
        "points": points,
        "score": participant.score,
        "round": round_public_state(state.round, private_state=state.private_state, deadline=state.deadline),
        "next_round": round_public_state(next_state.round, private_state=next_state.private_state, deadline=next_state.deadline) if next_state else None,
        "match": match_snapshot(match, participant),
    }
