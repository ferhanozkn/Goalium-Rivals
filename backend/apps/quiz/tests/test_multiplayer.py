from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.content.models import Question, QuestionPayload, QuestionTranslation, SourceReference
from apps.quiz.models import Match


User = get_user_model()


class MultiplayerApiTests(APITestCase):
    def setUp(self):
        source = SourceReference.objects.create(
            provider="Phase 4 test source",
            url="https://example.com/phase-4",
            license_name="Reference only",
            license_status="verified",
        )
        for index, mode in enumerate(("hangman", "career_path", "timed_trivia", "historical_score", "missing_lineup")):
            question = Question.objects.create(
                seed_key=f"phase4-test-{mode}",
                mode=mode,
                difficulty="easy",
                status="published",
                published_at=timezone.now(),
            )
            answer_data = {"correct_index": 0}
            choices = ["Doğru", "Yanlış", "Diğer", "Başka"]
            if mode == "hangman":
                answer_data = {"canonical": "gol"}
                choices = []
            elif mode == "career_path":
                answer_data = {"accepted_answers": {"tr": ["Iniesta"]}}
                choices = []
            elif mode == "historical_score":
                answer_data = {"regulation_home_goals": 0, "regulation_away_goals": 0, "final_result": "draw"}
                choices = []
            elif mode == "missing_lineup":
                answer_data = {"accepted_answers": {"tr": ["Griezmann"]}}
                choices = []
            QuestionPayload.objects.create(question=question, public_payload={}, answer_data=answer_data)
            QuestionTranslation.objects.create(
                question=question,
                language="tr",
                prompt=f"Faz 4 test sorusu {index}.",
                choices=choices,
                public_data={"entries": ["Barcelona"]} if mode == "career_path" else {},
            )
            question.source_references.add(source)

    def _guest(self, name):
        response = self.client.post(reverse("guest-session"), {"display_name": name}, format="json")
        self.assertEqual(response.status_code, 201)
        self.client.credentials(HTTP_X_GUEST_TOKEN=response.data["guest_token"])
        return response.data["guest_token"]

    def test_guest_room_waits_for_second_player_then_finishes_shared_round(self):
        first_token = self._guest("Room owner")
        created = self.client.post(
            reverse("rooms"),
            {"language": "tr", "is_mixed": False, "mode": "timed_trivia", "round_count": 1},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        room_code = created.data["match"]["room_code"]
        round_id = created.data["round"]
        self.assertIsNone(round_id)

        second_token = self._guest("Room player")
        joined = self.client.post(reverse("room-join", kwargs={"room_code": room_code}), {}, format="json")
        self.assertEqual(joined.status_code, 200, joined.data)

        self.client.credentials(HTTP_X_GUEST_TOKEN=first_token)
        started = self.client.post(reverse("room-start", kwargs={"room_code": room_code}), {}, format="json")
        self.assertEqual(started.status_code, 200, started.data)
        first_round = started.data["round"]
        self.assertEqual(started.data["match"]["status"], "live")

        first_answer = self.client.post(
            reverse("room-answers", kwargs={"room_code": room_code}),
            {"round_id": first_round["id"], "answer": {"choice_index": 0}},
            format="json",
        )
        self.assertEqual(first_answer.status_code, 200, first_answer.data)
        self.assertEqual(first_answer.data["phase"], "waiting")

        self.client.credentials(HTTP_X_GUEST_TOKEN=second_token)
        second_answer = self.client.post(
            reverse("room-answers", kwargs={"room_code": room_code}),
            {"round_id": first_round["id"], "answer": {"choice_index": 0}},
            format="json",
        )
        self.assertEqual(second_answer.status_code, 200, second_answer.data)
        self.assertEqual(second_answer.data["phase"], "finished")
        self.assertEqual(Match.objects.get(room_code=room_code).status, "finished")

    def test_accounts_play_same_question_set_in_async_duel(self):
        first = User.objects.create_user(email="first@example.com", password="strong-password-1", display_name="First")
        second = User.objects.create_user(email="second@example.com", password="strong-password-2", display_name="Second")

        self.client.force_authenticate(user=first)
        created = self.client.post(reverse("duels"), {"language": "tr", "modes": ["timed_trivia"]}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        duel_id = created.data["match"]["id"]
        first_round = created.data["round"]

        self.client.force_authenticate(user=second)
        joined = self.client.post(reverse("duel-join", kwargs={"duel_id": duel_id}), {}, format="json")
        self.assertEqual(joined.status_code, 200, joined.data)
        self.assertEqual(joined.data["round"]["id"], first_round["id"])
        self.assertEqual(joined.data["round"]["prompt"], first_round["prompt"])

        first_answer = self.client.post(
            reverse("duel-play", kwargs={"duel_id": duel_id}),
            {"round_id": first_round["id"], "answer": {"choice_index": 0}},
            format="json",
        )
        self.assertEqual(first_answer.status_code, 200, first_answer.data)
        self.assertEqual(first_answer.data["phase"], "waiting")

        self.client.force_authenticate(user=first)
        second_answer = self.client.post(
            reverse("duel-play", kwargs={"duel_id": duel_id}),
            {"round_id": first_round["id"], "answer": {"choice_index": 0}},
            format="json",
        )
        self.assertEqual(second_answer.status_code, 200, second_answer.data)
        self.assertEqual(second_answer.data["phase"], "finished")
        self.assertEqual(Match.objects.get(id=duel_id).status, "finished")

    def test_guest_cannot_create_async_duel(self):
        self._guest("Guest")
        response = self.client.post(reverse("duels"), {"language": "tr", "modes": ["timed_trivia"]}, format="json")

        self.assertIn(response.status_code, {401, 403})

    def test_async_duel_expiry_forfeits_invitational_owner(self):
        first = User.objects.create_user(email="owner@example.com", password="strong-password-1", display_name="Owner")
        self.client.force_authenticate(user=first)
        created = self.client.post(reverse("duels"), {"language": "tr", "modes": ["timed_trivia"]}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        match = Match.objects.get(id=created.data["match"]["id"])
        match.game_session.deadline = timezone.now() - timedelta(seconds=1)
        match.game_session.save(update_fields=["deadline"])

        detail = self.client.get(reverse("duel-detail", kwargs={"duel_id": match.id}))

        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["match"]["status"], "forfeit")
        self.assertEqual(detail.data["match"]["result"]["winner_participant_id"], str(created.data["participant_id"]))
