import json
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from django.test import TransactionTestCase

from apps.accounts.models import GuestSession
from apps.content.models import Question, QuestionPayload, QuestionTranslation, SourceReference
from apps.quiz.models import GameSession, Match, MatchParticipant, ParticipantRoundState, Round
from apps.quiz.services import create_live_match, join_live_match
from config.asgi import application


class MatchConsumerTests(TransactionTestCase):
    reset_sequences = True

    def test_guest_participant_can_connect_and_receive_state(self):
        guest, raw_token = GuestSession.issue("Realtime guest")
        match = create_live_match(
            {"user": None, "guest_session": guest, "display_name": guest.display_name},
            language="tr",
            is_mixed=True,
            origin="invite",
        )
        second_guest, second_raw_token = GuestSession.issue("Realtime rival")
        join_live_match(
            match,
            {"user": None, "guest_session": second_guest, "display_name": second_guest.display_name},
        )

        async def scenario():
            first_communicator = WebsocketCommunicator(
                application,
                f"/ws/v1/match/{match.id}/?guest_token={raw_token}",
            )
            second_communicator = WebsocketCommunicator(
                application,
                f"/ws/v1/match/{match.id}/?guest_token={second_raw_token}",
            )

            connected, _ = await first_communicator.connect()
            self.assertTrue(connected)

            state = await first_communicator.receive_json_from()
            self.assertEqual(state["type"], "match.state")
            self.assertEqual(state["status"], "live")
            self.assertEqual(state["participants"][0]["display_name"], "Realtime guest")

            connected, _ = await second_communicator.connect()
            self.assertTrue(connected)
            second_state = await second_communicator.receive_json_from()
            self.assertEqual(second_state["type"], "match.state")
            self.assertEqual(len(second_state["participants"]), 2)

            first_broadcast = await first_communicator.receive_json_from()
            self.assertEqual(first_broadcast["type"], "match.state")
            self.assertEqual(len(first_broadcast["participants"]), 2)

            await first_communicator.send_json_to({"type": "ping"})
            await second_communicator.send_json_to({"type": "ping"})
            self.assertEqual(await first_communicator.receive_json_from(), {"type": "pong"})
            self.assertEqual(await second_communicator.receive_json_from(), {"type": "pong"})
            await first_communicator.disconnect()
            await second_communicator.disconnect()

        async_to_sync(scenario)()

    def test_round_start_never_exposes_answer_data(self):
        source = SourceReference.objects.create(
            provider="Phase 6 realtime test",
            url="https://example.com/phase-6-realtime",
            license_name="Reference only",
            license_status="verified",
        )
        question = Question.objects.create(mode="hangman", difficulty="easy", status="published", published_at=timezone.now())
        QuestionPayload.objects.create(
            question=question,
            public_payload={"category": "term"},
            answer_data={"canonical": "gol"},
        )
        QuestionTranslation.objects.create(question=question, language="tr", prompt="Futbol kelimesini bulun.")
        QuestionTranslation.objects.create(question=question, language="en", prompt="Find the football term.")
        question.source_references.add(source)
        session = GameSession.objects.create(kind="live_1v1", modes=["hangman"], language="tr", status="active")
        match = Match.objects.create(
            game_session=session,
            match_type="live_1v1",
            origin="invite",
            is_mixed=False,
            language="tr",
            status="live",
        )
        guest, raw_token = GuestSession.issue("Public payload guest")
        participant = MatchParticipant.objects.create(match=match, guest_session=guest, display_name=guest.display_name)
        round_instance = Round.objects.create(
            match=match,
            question=question,
            order=0,
            mode="hangman",
            payload={"public_payload": {"category": "term"}},
            deadline=timezone.now() + timedelta(seconds=90),
            status="active",
        )
        ParticipantRoundState.objects.create(
            participant=participant,
            round=round_instance,
            deadline=round_instance.deadline,
            status="active",
        )

        async def scenario():
            communicator = WebsocketCommunicator(application, f"/ws/v1/match/{match.id}/?guest_token={raw_token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from()
            round_start = await communicator.receive_json_from()
            payload = json.dumps(round_start, ensure_ascii=False)
            self.assertEqual(round_start["type"], "round.start")
            self.assertNotIn("answer_data", payload)
            self.assertNotIn("canonical", payload)
            await communicator.disconnect()

        async_to_sync(scenario)()
