from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import GuestSession


class GuestPrincipal:
    is_authenticated = True
    is_anonymous = False

    def __init__(self, guest_session: GuestSession):
        self.guest_session = guest_session
        self.id = guest_session.id
        self.display_name = guest_session.display_name or "Guest"


class GuestTokenAuthentication(BaseAuthentication):
    keyword = "X-Guest-Token"

    def authenticate(self, request):
        raw_token = request.headers.get(self.keyword)
        if not raw_token:
            return None
        try:
            session = GuestSession.objects.get(token_hash=GuestSession.hash_token(raw_token))
        except GuestSession.DoesNotExist as exc:
            raise AuthenticationFailed("Geçersiz misafir oturumu.") from exc
        if session.expires_at <= timezone.now():
            raise AuthenticationFailed("Misafir oturumunun süresi dolmuş.")
        session.save(update_fields=["last_seen_at"])
        request.guest_session = session
        return GuestPrincipal(session), None
