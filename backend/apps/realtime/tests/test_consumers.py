from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from apps.accounts.models import GuestSession
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
