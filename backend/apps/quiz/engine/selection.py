from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.content.models import Question
from apps.quiz.engine.constants import mode_duration
from apps.quiz.models import GameSession, Match, Round


def select_question(session: GameSession, mode: str, allow_reuse: bool = False) -> Question:
    used_question_ids = session.match.rounds.exclude(question_id=None).values_list("question_id", flat=True)
    questions = (
        Question.objects.filter(status="published", mode=mode, translations__language=session.language)
        .exclude(id__in=used_question_ids)
        .prefetch_related("translations")
        .order_by("created_at")
    )
    question = questions.first()
    if question is None and (mode == "timed_trivia" or allow_reuse):
        question = (
            Question.objects.filter(status="published", mode=mode, translations__language=session.language)
            .prefetch_related("translations")
            .order_by("created_at")
            .first()
        )
    if question is None:
        raise ValidationError({"modes": f"{mode} için yayınlanmış soru bulunamadı."})
    return question


def create_round(
    session: GameSession,
    match: Match,
    mode: str,
    order: int,
    deadline=None,
    status="active",
    allow_reuse=False,
    update_session_deadline=True,
) -> Round:
    question = select_question(session, mode, allow_reuse=allow_reuse)
    translation = question.translations.filter(language=session.language).first()
    if translation is None:
        raise ValidationError({"language": "Seçilen dilde soru çevirisi bulunamadı."})
    now = timezone.now()
    deadline = deadline or now + timedelta(seconds=mode_duration(mode))
    if update_session_deadline and mode == "timed_trivia" and session.deadline != deadline:
        session.deadline = deadline
        session.save(update_fields=["deadline"])
    return Round.objects.create(
        match=match,
        question=question,
        order=order,
        mode=mode,
        payload={"public_payload": question.payload.public_payload},
        private_state={},
        deadline=deadline,
        status=status,
    )
