from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from django.utils import timezone

from apps.quiz.engine.multiplayer import _finish_match
from apps.quiz.models import GameSession, Match, MatchParticipant
from apps.ranking.engine import apply_rating_for_match, is_ranked_eligible
from apps.ranking.models import Rating, RatingEvent


User = get_user_model()


class FakeRedis:
    def __init__(self):
        self.zsets = {}
        self.hashes = {}
        self.values = {}

    def zscore(self, key, member):
        return self.zsets.get(key, {}).get(str(member))

    def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update({str(member): score for member, score in mapping.items()})

    def zcard(self, key):
        return len(self.zsets.get(key, {}))

    def zpopmin(self, key, count=1):
        values = sorted(self.zsets.get(key, {}).items(), key=lambda item: (item[1], item[0]))[:count]
        for member, _ in values:
            del self.zsets[key][member]
        return values

    def zrank(self, key, member):
        values = sorted(self.zsets.get(key, {}).items(), key=lambda item: (item[1], item[0]))
        try:
            return [item[0] for item in values].index(str(member))
        except ValueError:
            return None

    def hset(self, key, mapping):
        self.hashes[key] = mapping

    def expire(self, key, seconds):
        return True

    def set(self, key, value, ex=None):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        for key in keys:
            self.hashes.pop(key, None)
            self.values.pop(key, None)
        return True

    def zrem(self, key, member):
        return int(self.zsets.get(key, {}).pop(str(member), None) is not None)


class RatingEngineTests(APITestCase):
    def _users(self):
        first = User.objects.create_user(email="ranked-first@example.com", password="strong-password-1", display_name="First")
        second = User.objects.create_user(email="ranked-second@example.com", password="strong-password-2", display_name="Second")
        return first, second

    def _finished_ranked_match(self, winner_first=True, origin="matchmaking"):
        first, second = self._users()
        session = GameSession.objects.create(kind="live_1v1", modes=["hangman"], language="tr", status="finished")
        match = Match.objects.create(
            game_session=session,
            match_type="live_1v1",
            origin=origin,
            is_mixed=True,
            language="tr",
            status="finished",
        )
        first_participant = MatchParticipant.objects.create(match=match, user=first, display_name=first.display_name, score=100)
        second_participant = MatchParticipant.objects.create(match=match, user=second, display_name=second.display_name, score=50)
        match.result = {"winner_participant_id": str(first_participant.id if winner_first else second_participant.id), "draw": False}
        match.save(update_fields=["result"])
        return match, first, second

    def test_ranked_match_writes_two_events_and_second_processing_is_idempotent(self):
        match, first, second = self._finished_ranked_match()

        events = apply_rating_for_match(match)
        repeated = apply_rating_for_match(match)

        self.assertEqual(len(events), 2)
        self.assertEqual(len(repeated), 2)
        self.assertEqual(RatingEvent.objects.filter(match=match).count(), 2)
        self.assertEqual(Rating.objects.get(user=first).matches_played, 1)
        self.assertEqual(Rating.objects.get(user=second).matches_played, 1)
        self.assertEqual(Rating.objects.get(user=first).rating, 1024)
        self.assertEqual(Rating.objects.get(user=second).rating, 976)
        self.assertTrue(Match.objects.get(id=match.id).result["rating_applied"])

    def test_invite_match_is_not_ranked_even_when_scores_are_final(self):
        match, first, second = self._finished_ranked_match(origin="invite")

        self.assertFalse(is_ranked_eligible(match))
        self.assertEqual(apply_rating_for_match(match), [])
        self.assertEqual(Rating.objects.filter(user__in=[first, second]).count(), 0)

    def test_finishing_eligible_match_applies_rating_in_the_same_engine_path(self):
        match, first, second = self._finished_ranked_match()
        match.status = "live"
        match.game_session.status = "active"
        match.game_session.save(update_fields=["status"])
        match.save(update_fields=["status"])

        _finish_match(match, timezone.now())

        self.assertEqual(RatingEvent.objects.filter(match=match).count(), 2)
        self.assertEqual(Rating.objects.get(user=first).wins, 1)
        self.assertEqual(Rating.objects.get(user=second).losses, 1)

    def test_ranked_queue_pairs_two_accounts_and_creates_matchmaking_match(self):
        first, second = self._users()
        fake_redis = FakeRedis()

        with patch("apps.ranking.engine._redis_client", return_value=fake_redis):
            self.client.force_authenticate(user=first)
            waiting = self.client.post(reverse("matchmaking-queue"), {"language": "tr"}, format="json")
            self.assertEqual(waiting.status_code, 200, waiting.data)
            self.assertEqual(waiting.data["status"], "queued")

            self.client.force_authenticate(user=second)
            matched = self.client.post(reverse("matchmaking-queue"), {"language": "tr"}, format="json")
            self.client.force_authenticate(user=first)
            matched_status = self.client.get(reverse("matchmaking-queue-status"), {"language": "tr"})

        self.assertEqual(matched.status_code, 200, matched.data)
        self.assertEqual(matched.data["status"], "matched")
        self.assertEqual(matched.data["match"]["origin"], "matchmaking")
        self.assertTrue(matched.data["match"]["ranked_eligible"])
        self.assertEqual(MatchParticipant.objects.filter(match_id=matched.data["match"]["id"]).count(), 2)
        self.assertEqual(matched_status.status_code, 200, matched_status.data)
        self.assertEqual(matched_status.data["status"], "matched")

    def test_stats_and_global_leaderboard_are_account_only_and_persistent(self):
        match, first, second = self._finished_ranked_match()
        apply_rating_for_match(match)

        self.client.force_authenticate(user=first)
        stats = self.client.get(reverse("me-stats"))
        leaderboard = self.client.get(reverse("leaderboard"))

        self.assertEqual(stats.status_code, 200, stats.data)
        self.assertEqual(stats.data["matches_played"], 1)
        self.assertEqual(stats.data["rating"], 1024)
        self.assertEqual(leaderboard.status_code, 200, leaderboard.data)
        self.assertEqual(leaderboard.data["entries"][0]["display_name"], first.display_name)
        self.assertEqual(leaderboard.data["entries"][0]["rating"], 1024)
        self.assertNotEqual(first.id, second.id)
