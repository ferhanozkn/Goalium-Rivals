from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from apps.content.constants import LANGUAGE_CHOICES
from apps.content.models import Question, SourceReference
from apps.content.serializers import (
    QuestionEditorSerializer,
    QuestionPublicSerializer,
    SourceReferenceSerializer,
)
from apps.content.services import transition_question


EDITOR_AUTHENTICATION = [JWTAuthentication, SessionAuthentication]
VALID_LANGUAGES = {language for language, _ in LANGUAGE_CHOICES}


def requested_language(request):
    language = request.query_params.get("language", "tr").lower()
    return language if language in VALID_LANGUAGES else "tr"


@extend_schema(
    parameters=[OpenApiParameter("language", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=sorted(VALID_LANGUAGES))],
    responses=QuestionPublicSerializer(many=True),
    tags=["content"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def public_questions(request):
    language = requested_language(request)
    questions = (
        Question.objects.filter(status="published", translations__language=language)
        .prefetch_related("translations")
        .select_related("payload")
        .distinct()
    )
    return Response(QuestionPublicSerializer(questions, many=True, context={"language": language}).data)


@extend_schema(
    parameters=[OpenApiParameter("language", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=sorted(VALID_LANGUAGES))],
    responses=QuestionPublicSerializer,
    tags=["content"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def public_question_detail(request, question_id):
    language = requested_language(request)
    question = (
        Question.objects.filter(id=question_id, status="published", translations__language=language)
        .prefetch_related("translations")
        .select_related("payload")
        .first()
    )
    if question is None:
        return Response({"detail": "Soru bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    return Response(QuestionPublicSerializer(question, context={"language": language}).data)


@extend_schema(
    request=SourceReferenceSerializer,
    responses={201: SourceReferenceSerializer},
    tags=["content-editor"],
)
@api_view(["POST"])
@authentication_classes(EDITOR_AUTHENTICATION)
@permission_classes([IsAdminUser])
def editor_sources(request):
    serializer = SourceReferenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    source = serializer.save()
    return Response(SourceReferenceSerializer(source).data, status=status.HTTP_201_CREATED)


@extend_schema(
    request=QuestionEditorSerializer,
    responses={201: QuestionEditorSerializer},
    tags=["content-editor"],
)
@api_view(["POST"])
@authentication_classes(EDITOR_AUTHENTICATION)
@permission_classes([IsAdminUser])
def editor_questions(request):
    serializer = QuestionEditorSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    question = serializer.save(created_by=request.user)
    return Response(QuestionEditorSerializer(question).data, status=status.HTTP_201_CREATED)


@extend_schema(responses={200: QuestionEditorSerializer}, tags=["content-editor"])
@api_view(["GET"])
@authentication_classes(EDITOR_AUTHENTICATION)
@permission_classes([IsAdminUser])
def editor_question_detail(request, question_id):
    question = Question.objects.prefetch_related("translations", "source_references").select_related("payload").filter(id=question_id).first()
    if question is None:
        return Response({"detail": "Soru bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    return Response(QuestionEditorSerializer(question).data)


@extend_schema(
    request={"application/json": {"type": "object", "properties": {"target_status": {"type": "string"}}}},
    responses={200: QuestionEditorSerializer},
    tags=["content-editor"],
)
@api_view(["POST"])
@authentication_classes(EDITOR_AUTHENTICATION)
@permission_classes([IsAdminUser])
def editor_question_transition(request, question_id):
    target_status = request.data.get("target_status")
    if not isinstance(target_status, str):
        return Response({"detail": "target_status zorunludur."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        question = transition_question(question_id, target_status, request.user)
    except Question.DoesNotExist:
        return Response({"detail": "Soru bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
    except ValidationError as exc:
        return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    return Response(QuestionEditorSerializer(question).data)
