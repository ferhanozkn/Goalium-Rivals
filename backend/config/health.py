import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(responses={200: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT}, tags=["system"])
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    checks = {"database": "ok", "redis": "ok"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        checks["database"] = "error"
    try:
        redis.Redis.from_url(settings.REDIS_URL, decode_responses=True).ping()
    except Exception:
        checks["redis"] = "error"
    status_code = 200 if all(value == "ok" for value in checks.values()) else 503
    return Response({"status": "ok" if status_code == 200 else "error", **checks}, status=status_code)
