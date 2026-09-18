import math
import json
import time
from collections import defaultdict
from datetime import datetime, timezone as datetime_timezone
from typing import Any

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.quiz.models import Match, MatchParticipant
from apps.ranking.models import Rating, RatingEvent


STARTING_RATING = 1000
NORMAL_K = 32
PLACEMENT_K = 48
PLACEMENT_MATCHES = 10
MATCHMAKING_QUEUE_PREFIX = "goalium:matchmaking:ranked"
MATCHMAKING_TICKET_TTL = 600
MATCHMAKING_RESULT_TTL = 600

User = get_user_model()


def is_ranked_eligible(match: Match) -> bool:
    """The single gate for shared ranked rating changes."""
    return match.match_type == "live_1v1" and match.is_mixed and match.origin == "matchmaking"


def ensure_rating(user) -> Rating:
    rating, _ = Rating.objects.get_or_create(user=user, defaults={"rating": STARTING_RATING})
    return rating


def _redis_client():
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _queue_key(language: str) -> str:
    return f"{MATCHMAKING_QUEUE_PREFIX}:{language}"


def _ticket_key(language: str, user_id: str) -> str:
    return f"{MATCHMAKING_QUEUE_PREFIX}:ticket:{language}:{user_id}"


def _result_key(language: str, user_id: str) -> str:
    return f"{MATCHMAKING_QUEUE_PREFIX}:result:{language}:{user_id}"


def _queue_entry(user_id: str, language: str) -> dict[str, str]:
    return {"user_id": user_id, "language": language}


def _match_queued_users(language: str, client) -> tuple[Match, MatchParticipant] | None:
    queue_key = _queue_key(language)
    if client.zcard(queue_key) < 2:
        return None

    entries = client.zpopmin(queue_key, count=2)
    if len(entries) < 2:
        for member, score in entries:
            client.zadd(queue_key, {member: score})
        return None

    user_ids = [str(member) for member, _ in entries]
    users = {str(user.id): user for user in User.objects.filter(id__in=user_ids, is_active=True)}
    if len(users) != 2:
        for user_id in user_ids:
            client.delete(_ticket_key(language, user_id))
        return None

    first_user = users[user_ids[0]]
    second_user = users[user_ids[1]]
    with transaction.atomic():
        from apps.quiz.services import create_live_match, join_live_match

        match = create_live_match(
            {"user": first_user, "guest_session": None, "display_name": first_user.display_name},
            language=language,
            is_mixed=True,
            origin="matchmaking",
        )
        participant = join_live_match(
            match,
            {"user": second_user, "guest_session": None, "display_name": second_user.display_name},
        )

    participants = {str(item.user_id): item for item in match.participants.filter(user__isnull=False)}
    for user_id in user_ids:
        client.delete(_ticket_key(language, user_id))
        client.set(
            _result_key(language, user_id),
            json.dumps({"match_id": str(match.id), "participant_id": str(participants[user_id].id)}),
            ex=MATCHMAKING_RESULT_TTL,
        )
    return match, participant


def _matched_result(user, language: str, client) -> dict[str, Any] | None:
    raw = client.get(_result_key(language, str(user.id)))
    if not raw:
        return None
    payload = json.loads(raw)
    match = Match.objects.filter(id=payload["match_id"], match_type="live_1v1").first()
    participant = match.participants.filter(id=payload["participant_id"]).first() if match else None
    if match is None or participant is None:
        return None
    return {"status": "matched", "queue": "ranked", "match": match, "participant": participant}


def enqueue_matchmaking(user, *, language: str = "tr") -> dict[str, Any]:
    ensure_rating(user)
    client = _redis_client()
    queue_key = _queue_key(language)
    user_id = str(user.id)
    ticket_key = _ticket_key(language, user_id)
    already_matched = _matched_result(user, language, client)
    if already_matched:
        return already_matched
    if client.zscore(queue_key, user_id) is None:
        client.zadd(queue_key, {user_id: time.time()})
        client.hset(ticket_key, mapping=_queue_entry(user_id, language))
        client.expire(ticket_key, MATCHMAKING_TICKET_TTL)

    matched = _match_queued_users(language, client)
    if matched:
        match, participant = matched
        return {"status": "matched", "queue": "ranked", "match": match, "participant": participant}

    position = client.zrank(queue_key, user_id)
    return {"status": "queued", "queue": "ranked", "position": (position + 1) if position is not None else 1}


def dequeue_matchmaking(user, *, language: str = "tr") -> bool:
    client = _redis_client()
    removed = client.zrem(_queue_key(language), str(user.id))
    client.delete(_ticket_key(language, str(user.id)))
    return bool(removed)


def matchmaking_status(user, *, language: str = "tr") -> dict[str, Any]:
    client = _redis_client()
    already_matched = _matched_result(user, language, client)
    if already_matched:
        return already_matched
    queue_key = _queue_key(language)
    position = client.zrank(queue_key, str(user.id))
    return {
        "status": "queued" if position is not None else "idle",
        "queue": "ranked",
        "position": (position + 1) if position is not None else None,
    }


def _rounded_delta(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _expected_score(rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def _outcomes(match: Match, participants: list[MatchParticipant]) -> dict[str, float]:
    winner_id = str((match.result or {}).get("winner_participant_id") or "")
    draw = bool((match.result or {}).get("draw"))
    if draw or not winner_id:
        return {str(participant.id): 0.5 for participant in participants}
    return {str(participant.id): (1.0 if str(participant.id) == winner_id else 0.0) for participant in participants}


@transaction.atomic
def apply_rating_for_match(match: Match) -> list[RatingEvent]:
    match = Match.objects.select_for_update().get(id=match.id)
    if not is_ranked_eligible(match) or match.status not in {"finished", "forfeit"}:
        return []

    participants = list(
        MatchParticipant.objects.filter(match=match, user__isnull=False).select_related("user").order_by("user_id")
    )
    if len(participants) != 2:
        return []

    existing = list(RatingEvent.objects.filter(match=match).order_by("user_id"))
    if len(existing) == len(participants):
        return existing
    if existing:
        raise RuntimeError("Eksik rating event bulundu; atomik maç sonucu yeniden işlenemiyor.")

    ratings_by_user = {}
    for participant in participants:
        ensure_rating(participant.user)
    locked_ratings = Rating.objects.select_for_update().filter(user__in=[item.user for item in participants]).order_by("user_id")
    for rating in locked_ratings:
        ratings_by_user[str(rating.user_id)] = rating

    outcomes = _outcomes(match, participants)
    deltas_by_user: dict[str, int] = {}
    deltas_by_participant: dict[str, int] = {}
    for participant in participants:
        own = ratings_by_user[str(participant.user_id)]
        opponent = next(item for item in participants if item.user_id != participant.user_id)
        opponent_rating = ratings_by_user[str(opponent.user_id)].rating
        k_factor = PLACEMENT_K if own.matches_played < PLACEMENT_MATCHES else NORMAL_K
        delta = _rounded_delta(k_factor * (outcomes[str(participant.id)] - _expected_score(own.rating, opponent_rating)))
        deltas_by_user[str(participant.user_id)] = delta
        deltas_by_participant[str(participant.id)] = delta

    events = []
    for participant in participants:
        user_key = str(participant.user_id)
        own = ratings_by_user[user_key]
        score = outcomes[str(participant.id)]
        delta = deltas_by_user[user_key]
        previous_rating = own.rating
        own.rating = max(0, own.rating + delta)
        own.matches_played += 1
        if score == 1.0:
            own.wins += 1
            outcome = "win"
        elif score == 0.5:
            own.draws += 1
            outcome = "draw"
        else:
            own.losses += 1
            outcome = "loss"
        own.save(update_fields=["rating", "matches_played", "wins", "draws", "losses", "updated_at"])
        events.append(
            RatingEvent.objects.create(
                match=match,
                user=participant.user,
                previous_rating=previous_rating,
                new_rating=own.rating,
                delta=delta,
                outcome=outcome,
            )
        )

    match.result = {
        **(match.result or {}),
        "rating_applied": True,
        "rating_deltas": deltas_by_participant,
    }
    match.save(update_fields=["result"])
    return events


def _ranked_entries(period: str, season: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if period == "global":
        rows = list(Rating.objects.select_related("user").order_by("-rating", "-matches_played", "user__display_name")[:limit])
        return [
            {
                "rank": index,
                "user_id": str(row.user_id),
                "display_name": row.user.display_name,
                "rating": row.rating,
                "matches_played": row.matches_played,
                "wins": row.wins,
                "draws": row.draws,
                "losses": row.losses,
                "in_placement": row.in_placement,
            }
            for index, row in enumerate(rows, start=1)
        ]

    season_key = season or str(timezone.now().year)
    start = datetime(int(season_key), 1, 1, tzinfo=datetime_timezone.utc)
    end = datetime(int(season_key) + 1, 1, 1, tzinfo=datetime_timezone.utc)
    aggregate = defaultdict(lambda: {"delta": 0, "matches_played": 0, "wins": 0, "draws": 0, "losses": 0})
    events = RatingEvent.objects.filter(created_at__gte=start, created_at__lt=end).select_related("user")
    for event in events:
        values = aggregate[str(event.user_id)]
        values["delta"] += event.delta
        values["matches_played"] += 1
        values[{"win": "wins", "draw": "draws", "loss": "losses"}[event.outcome]] += 1
    users = {str(user.id): user for user in User.objects.filter(id__in=aggregate.keys())}
    rows = sorted(
        (
            {"user": users[user_id], "rating": STARTING_RATING + values["delta"], **values}
            for user_id, values in aggregate.items()
            if user_id in users
        ),
        key=lambda row: (-row["rating"], -row["matches_played"], row["user"].display_name),
    )[:limit]
    return [
        {
            "rank": index,
            "user_id": str(row["user"].id),
            "display_name": row["user"].display_name,
            "rating": row["rating"],
            "matches_played": row["matches_played"],
            "wins": row["wins"],
            "draws": row["draws"],
            "losses": row["losses"],
            "in_placement": row["matches_played"] < PLACEMENT_MATCHES,
        }
        for index, row in enumerate(rows, start=1)
    ]


def leaderboard(*, period: str = "global", season: str | None = None, limit: int = 50) -> dict[str, Any]:
    season_key = season or str(timezone.now().year)
    return {"period": period, "season": season_key if period == "season" else None, "entries": _ranked_entries(period, season_key, limit)}


def user_stats(user) -> dict[str, Any]:
    rating = ensure_rating(user)
    global_entries = _ranked_entries("global", limit=Rating.objects.count() or 1)
    global_rank = next((entry["rank"] for entry in global_entries if entry["user_id"] == str(user.id)), None)
    season_data = leaderboard(period="season")
    season_rank = next((entry["rank"] for entry in season_data["entries"] if entry["user_id"] == str(user.id)), None)
    return {
        "user_id": str(user.id),
        "display_name": user.display_name,
        "rating": rating.rating,
        "matches_played": rating.matches_played,
        "wins": rating.wins,
        "draws": rating.draws,
        "losses": rating.losses,
        "in_placement": rating.in_placement,
        "global_rank": global_rank,
        "season_rank": season_rank,
    }
