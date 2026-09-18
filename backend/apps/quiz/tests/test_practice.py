from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.content.models import Question, QuestionPayload, QuestionTranslation, SourceReference
from apps.quiz.models import GameSession


class PracticeApiTests(APITestCase):
    def setUp(self):
        source = SourceReference.objects.create(
            provider="Test source",
            url="https://example.com/phase-3",
            license_name="Reference only",
            license_status="verified",
        )
        questions = [
            {
                "seed_key": "test-hangman",
                "mode": "hangman",
                "answer_data": {"canonical": "ofsayt"},
                "prompt": "Futbolda savunma çizgisiyle ilgili kural nedir?",
                "public_data": {},
            },
            {
                "seed_key": "test-career",
                "mode": "career_path",
                "answer_data": {"accepted_answers": {"tr": ["iniesta"]}},
                "prompt": "Bu kariyer yolu hangi oyuncuya ait?",
                "public_data": {"entries": ["FC Barcelona", "Spain"]},
            },
            {
                "seed_key": "test-timed",
                "mode": "timed_trivia",
                "answer_data": {"correct_index": 0},
                "prompt": "2010 Dünya Kupası finalinde golü kim attı?",
                "public_data": {},
            },
            {
                "seed_key": "test-history",
                "mode": "historical_score",
                "answer_data": {
                    "regulation_home_goals": 0,
                    "regulation_away_goals": 0,
                    "final_result": "away",
                },
                "prompt": "2010 finalinin normal süredeki skoru neydi?",
                "public_data": {"home_team": "Hollanda", "away_team": "İspanya"},
            },
            {
                "seed_key": "test-lineup",
                "mode": "missing_lineup",
                "answer_data": {"accepted_answers": {"tr": ["griezmann"]}},
                "prompt": "Eksik oyuncuyu bul.",
                "public_data": {"team": "Fransa", "formation": "4-2-3-1", "slots": ["GK", "DF", "MF", "FW"]},
            },
        ]
        for item in questions:
            question = Question.objects.create(
                seed_key=item["seed_key"],
                mode=item["mode"],
                difficulty="medium",
                status="published",
                published_at=timezone.now(),
            )
            QuestionPayload.objects.create(question=question, public_payload={}, answer_data=item["answer_data"])
            QuestionTranslation.objects.create(
                question=question,
                language="tr",
                prompt=item["prompt"],
                choices=["Andrés Iniesta", "Xavi Hernández"] if item["mode"] == "timed_trivia" else [],
                hints=["Bir İspanyol futbolcuyu düşün."] if item["mode"] == "career_path" else [],
                public_data=item["public_data"],
            )
            question.source_references.add(source)

    def _guest_auth(self):
        response = self.client.post(reverse("guest-session"), {"display_name": "Phase 3 tester"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.client.credentials(HTTP_X_GUEST_TOKEN=response.data["guest_token"])

    def _start(self, modes):
        self._guest_auth()
        response = self.client.post(
            reverse("practice-sessions"),
            {"language": "tr", "modes": modes},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def _answer(self, session_id, round_id, answer):
        return self.client.post(
            reverse("practice-answers", kwargs={"session_id": session_id}),
            {"round_id": round_id, "answer": answer},
            format="json",
        )

    def test_all_five_modes_are_server_authoritative_and_complete(self):
        data = self._start(["hangman", "career_path", "timed_trivia", "historical_score", "missing_lineup"])
        session_id = data["session"]["id"]
        round_state = data["round"]

        self.assertNotIn("answer_data", round_state)
        self.assertNotIn("canonical", str(round_state))
        self.assertEqual(round_state["mode"], "hangman")

        for letter in "ofsayt":
            response = self._answer(session_id, round_state["id"], {"letter": letter})
            self.assertEqual(response.status_code, 200, response.data)
            if response.data["next_round"]:
                self.assertEqual(response.data["result"], "correct")
                round_state = response.data["next_round"]

        self.assertEqual(round_state["mode"], "career_path")
        response = self._answer(session_id, round_state["id"], {"text": "Iniesta"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["result"], "correct")
        round_state = response.data["next_round"]

        self.assertEqual(round_state["mode"], "timed_trivia")
        response = self._answer(session_id, round_state["id"], {"choice_index": 0})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["result"], "correct")
        round_state = response.data["next_round"]

        self.assertEqual(round_state["mode"], "historical_score")
        response = self._answer(session_id, round_state["id"], {"home": 0, "away": 1})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["result"], "correct")
        self.assertGreater(response.data["points"], 0)
        round_state = response.data["next_round"]

        self.assertEqual(round_state["mode"], "missing_lineup")
        response = self._answer(session_id, round_state["id"], {"text": "Griezmann"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["result"], "correct")
        self.assertIsNone(response.data["next_round"])
        self.assertEqual(GameSession.objects.get(id=session_id).status, "finished")

    def test_timed_trivia_wrong_answer_reduces_server_deadline(self):
        data = self._start(["timed_trivia"])
        session_id = data["session"]["id"]
        round_state = data["round"]

        response = self._answer(session_id, round_state["id"], {"choice_index": 1})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["result"], "wrong")
        self.assertEqual(response.data["next_round"]["mode"], "timed_trivia")
        first_deadline = round_state["deadline"]
        next_deadline = response.data["next_round"]["deadline"]
        deadline_delta = (first_deadline - next_deadline).total_seconds()
        self.assertGreater(deadline_delta, 2)
        self.assertLess(deadline_delta, 4)
