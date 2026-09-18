from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.content.models import Question


ALLOWED_TRANSITIONS = {
    "draft": {"in_review"},
    "in_review": {"draft", "approved"},
    "approved": {"in_review", "published"},
    "published": {"retired"},
    "retired": set(),
}


@transaction.atomic
def transition_question(question_id, target_status, actor):
    question = Question.objects.select_for_update().get(id=question_id)
    if target_status not in ALLOWED_TRANSITIONS[question.status]:
        raise ValidationError({"status": f"{question.status} durumundan {target_status} durumuna geçilemez."})
    if target_status == "published":
        question.validate_publishable()
    now = timezone.now()
    question.status = target_status
    if target_status == "approved":
        question.approved_by = actor
        question.approved_at = now
    if target_status == "published":
        question.published_at = now
    if target_status == "retired":
        question.published_at = question.published_at or now
    question.save(update_fields=["status", "approved_by", "approved_at", "published_at", "updated_at"])
    return question
