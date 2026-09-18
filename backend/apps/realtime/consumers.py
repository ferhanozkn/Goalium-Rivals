import hashlib
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import GuestSession
from apps.quiz.engine.multiplayer import MultiplayerConflict, submit_multiplayer_answer
from apps.quiz.engine.practice import round_public_state
from apps.quiz.models import Match, MatchParticipant, ParticipantRoundState

User = get_user_model()


class MatchConsumer(AsyncJsonWebsocketConsumer):
    @staticmethod
    def serialize_round_state(state):
        if state is None:
            return None
        serialized = dict(state)
        for key in ("deadline", "server_now"):
            value = serialized.get(key)
            if hasattr(value, "isoformat"):
                serialized[key] = value.isoformat()
        return serialized

    @classmethod
    def serialize_answer_result(cls, result):
        serialized = dict(result)
        serialized["round"] = cls.serialize_round_state(serialized.get("round"))
        serialized["next_round"] = cls.serialize_round_state(serialized.get("next_round"))
        return serialized

    async def connect(self):
        self.match_id = self.scope["url_route"]["kwargs"]["match_id"]
        self.group_name = f"match_{self.match_id}"
        identity = await self.resolve_identity()
        if identity is None:
            await self.close(code=4401)
            return
        participant = await self.get_participant(identity)
        if participant is None:
            await self.close(code=4403)
            return
        self.participant_id = str(participant.id)
        await self.mark_connected(True)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_match_state()
        await self.send_current_round()
        await self.channel_layer.group_send(self.group_name, {"type": "match.state"})

    async def disconnect(self, close_code):
        if hasattr(self, "participant_id"):
            await self.mark_connected(False)
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.channel_layer.group_send(self.group_name, {"type": "match.state"})

    async def receive_json(self, content, **kwargs):
        message_type = content.get("type")
        if message_type == "ping":
            await self.send_json({"type": "pong"})
            return
        if message_type == "rejoin":
            await self.send_match_state()
            return
        if message_type == "answer.submit":
            round_id = content.get("round_id")
            answer = content.get("answer")
            if not round_id or not isinstance(answer, dict):
                await self.send_json({"type": "error", "code": "INVALID_ANSWER", "message": "round_id ve answer zorunludur."})
                return
            try:
                result = await self.submit_answer(round_id, answer)
            except (Match.DoesNotExist, ParticipantRoundState.DoesNotExist):
                await self.send_json({"type": "error", "code": "ROUND_NOT_FOUND", "message": "Tur bulunamadı."})
                return
            except (MultiplayerConflict, ValidationError, ValueError) as exc:
                await self.send_json({"type": "error", "code": "ANSWER_REJECTED", "message": str(exc)})
                return
            await self.send_json({"type": "answer.result", **self.serialize_answer_result(result)})
            await self.channel_layer.group_send(self.group_name, {"type": "match.state"})
            if result.get("phase") in {"advanced", "finished"}:
                await self.channel_layer.group_send(self.group_name, {"type": "round.start"})
            return
        await self.send_json({"type": "error", "code": "UNKNOWN_MESSAGE", "message": "Bilinmeyen mesaj türü."})

    async def match_state(self, event):
        await self.send_match_state()

    async def round_start(self, event):
        await self.send_current_round()

    async def send_match_state(self):
        state = await self.get_match_state()
        if state:
            await self.send_json({"type": "match.state", **state})

    async def send_current_round(self):
        state = await self.get_current_round()
        if state:
            await self.send_json({"type": "round.start", **self.serialize_round_state(state)})

    async def resolve_identity(self):
        params = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        access_token = params.get("token", [None])[0]
        guest_token = params.get("guest_token", [None])[0]
        if access_token:
            try:
                token = AccessToken(access_token)
                return {"user_id": str(token["user_id"]), "guest_token": None}
            except Exception:
                return None
        if guest_token:
            return {"user_id": None, "guest_token": guest_token}
        return None

    @database_sync_to_async
    def get_participant(self, identity):
        match = Match.objects.filter(id=self.match_id).first()
        if match is None:
            return None
        if identity["user_id"]:
            return MatchParticipant.objects.filter(match=match, user_id=identity["user_id"]).first()
        try:
            guest = GuestSession.objects.get(token_hash=GuestSession.hash_token(identity["guest_token"]))
        except GuestSession.DoesNotExist:
            return None
        if guest.expires_at <= timezone.now():
            return None
        return MatchParticipant.objects.filter(match=match, guest_session=guest).first()

    @database_sync_to_async
    def mark_connected(self, connected):
        MatchParticipant.objects.filter(id=self.participant_id).update(connected=connected, last_seen_at=timezone.now())

    @database_sync_to_async
    def get_match_state(self):
        match = Match.objects.prefetch_related("participants").filter(id=self.match_id).first()
        if match is None:
            return None
        return {
            "match_id": str(match.id),
            "status": match.status,
            "match_type": match.match_type,
            "is_mixed": match.is_mixed,
            "language": match.language,
            "result": match.result,
            "participants": [
                {
                    "id": str(participant.id),
                    "display_name": participant.display_name,
                    "score": participant.score,
                    "connected": participant.connected,
                }
                for participant in match.participants.all()
            ],
        }

    @database_sync_to_async
    def get_current_round(self):
        participant = MatchParticipant.objects.select_related("match").filter(id=self.participant_id).first()
        if participant is None:
            return None
        state = (
            ParticipantRoundState.objects.select_related("round", "round__question", "round__match")
            .filter(participant=participant, status="active")
            .order_by("round__order")
            .first()
        )
        if state is None:
            return None
        return round_public_state(state.round, private_state=state.private_state, deadline=state.deadline)

    @database_sync_to_async
    def submit_answer(self, round_id, answer):
        return submit_multiplayer_answer(self.match_id, self.participant_id, round_id, answer)
