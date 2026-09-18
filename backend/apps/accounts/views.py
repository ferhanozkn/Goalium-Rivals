from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema

from apps.accounts.authentication import GuestTokenAuthentication
from apps.accounts.models import GuestSession
from apps.accounts.serializers import (
    AuthResponseSerializer,
    GuestSessionCreateSerializer,
    GuestSessionResponseSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    token_pair_for,
)

User = get_user_model()


@extend_schema(request=RegisterSerializer, responses={201: AuthResponseSerializer}, tags=["auth"])
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response({"user": UserSerializer(user).data, "tokens": token_pair_for(user)}, status=status.HTTP_201_CREATED)


@extend_schema(request=LoginSerializer, responses={200: AuthResponseSerializer}, tags=["auth"])
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    return Response({"user": UserSerializer(user).data, "tokens": token_pair_for(user)})


@extend_schema(request=GuestSessionCreateSerializer, responses={201: GuestSessionResponseSerializer}, tags=["auth"])
@api_view(["POST"])
@permission_classes([AllowAny])
def guest_session(request):
    display_name = str(request.data.get("display_name", "")).strip()
    session, raw_token = GuestSession.issue(display_name)
    return Response(
        {
            "guest_token": raw_token,
            "guest_session_id": str(session.id),
            "display_name": session.display_name,
            "expires_at": session.expires_at,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(responses={200: UserSerializer}, tags=["auth"])
@api_view(["GET"])
@authentication_classes([JWTAuthentication, GuestTokenAuthentication])
@permission_classes([IsAuthenticated])
def me(request):
    if hasattr(request, "guest_session"):
        session = request.guest_session
        return Response(
            {
                "type": "guest",
                "id": str(session.id),
                "display_name": session.display_name,
                "expires_at": session.expires_at,
            }
        )
    return Response({"type": "user", **UserSerializer(request.user).data})
