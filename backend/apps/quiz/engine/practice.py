import json
import math
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.quiz.engine.constants import MODE_RULES
from apps.quiz.engine.normalization import is_accepted_answer, normalize_answer
from apps.quiz.engine.selection import create_round
from apps.quiz.models import Answer, GameSession, Match, MatchParticipant, Round


class PracticeRoundConflict(ValidationError):
    pass


def create_practice_session(actor, modes: list[str], language: str):
    if not modes:
        raise ValidationError({"modes": "En az bir oyun modu seçilmelidir."})
    unknown_modes = sorted(set(modes) - set(MODE_RULES))
    if unknown_modes:
        raise ValidationError({"modes": f"Desteklenmeyen oyun modları: {', '.join(unknown_modes)}."})

    with transaction.atomic():
        session = GameSession.objects.create(
            kind="practice",
            modes=modes,
            language=language,
            status="active",
            started_at=timezone.now(),
        )
        match = Match.objects.create(
            game_session=session,
            match_type="practice",
            origin="practice",
            is_mixed=len(modes) > 1,
            language=language,
            status="live",
            max_players=1,
            started_at=session.started_at,
        )
        participant = MatchParticipant.objects.create(
            match=match,
            user=actor["user"],
            guest_session=actor["guest_session"],
            display_name=actor["display_name"],
        )
        round_instance = create_round(session, match, modes[0], 0)
    return session, match, participant, round_instance


def get_practice_participant(session_id, actor) -> MatchParticipant:
    participant_filter = {"match__game_session_id": session_id}
    if actor["user"] is not None:
        participant_filter["user"] = actor["user"]
    else:
        participant_filter["guest_session"] = actor["guest_session"]
    participant = MatchParticipant.objects.select_related("match", "match__game_session").filter(**participant_filter).first()
    if participant is None or participant.match.match_type != "practice":
        raise ValidationError({"session": "Pratik oturumu bulunamadı."})
    return participant


def round_public_state(round_instance: Round, now=None) -> dict:
    now = now or timezone.now()
    question = round_instance.question
    translation = question.translations.filter(language=round_instance.match.language).first()
    if translation is None:
        raise ValidationError({"language": "Tur çevirisi bulunamadı."})
    state = round_instance.private_state or {}
    public_data = dict(round_instance.payload.get("public_payload") or {})
    public_data.update(translation.public_data or {})
    if round_instance.mode == "hangman":
        canonical = str(question.payload.answer_data.get("canonical", ""))
        guessed_letters = set(state.get("guessed_letters", []))
        normalized_canonical = normalize_answer(canonical, round_instance.match.language)
        pattern = " ".join(
            character if not character.isalpha() or normalize_answer(character, round_instance.match.language) in guessed_letters else "_"
            for character in normalized_canonical
        )
        public_data["pattern"] = pattern
        public_data["wrong_letters"] = state.get("wrong_letters", [])
        public_data["hint_count"] = state.get("hint_count", 0)
        public_data["max_hints"] = MODE_RULES["hangman"]["max_hints"]
        public_data["max_wrong_letters"] = MODE_RULES["hangman"]["max_wrong_letters"]
    elif round_instance.mode == "career_path":
        entries = list(public_data.get("entries", []))
        elapsed = max(0, int((now - round_instance.created_at).total_seconds()))
        visible_entries = min(len(entries), 1 + elapsed // MODE_RULES["career_path"]["entry_reveal_interval"])
        public_data["entries"] = entries[:visible_entries]
        public_data["visible_entries"] = visible_entries
        public_data["max_attempts"] = MODE_RULES["career_path"]["max_attempts"]
        public_data["attempts_used"] = state.get("attempts_used", 0)
    elif round_instance.mode == "missing_lineup":
        public_data["attempts_used"] = state.get("attempts_used", 0)
        public_data["max_attempts"] = MODE_RULES["missing_lineup"]["max_attempts"]
        public_data["found_count"] = len(state.get("found_indices", []))
        public_data["hidden_count"] = int(public_data.get("hidden_count", 1))

    return {
        "id": str(round_instance.id),
        "order": round_instance.order,
        "mode": round_instance.mode,
        "status": round_instance.status,
        "deadline": round_instance.deadline,
        "server_now": now,
        "prompt": translation.prompt,
        "choices": translation.choices,
        "hints": translation.hints,
        "data": public_data,
    }


def _json_answer(answer) -> str:
    if isinstance(answer, str):
        return answer
    return json.dumps(answer, ensure_ascii=False, sort_keys=True)


def _answer_value(answer, key=None):
    if key is not None and isinstance(answer, dict):
        return answer.get(key)
    return answer


def _remaining_seconds(round_instance: Round, now) -> int:
    return max(0, math.floor((round_instance.deadline - now).total_seconds()))


def _final_answer(round_instance, participant, answer, result, points, now):
    Answer.objects.create(
        round=round_instance,
        participant=participant,
        raw_answer=_json_answer(answer),
        normalized_answer=normalize_answer(_json_answer(answer), round_instance.match.language),
        result=result,
        response_ms=max(0, int((now - round_instance.created_at).total_seconds() * 1000)),
        points=points,
    )
    round_instance.status = "timeout" if result == "timeout" else "finished"
    round_instance.save(update_fields=["status", "private_state"])
    MatchParticipant.objects.filter(id=participant.id).update(score=F("score") + points)
    participant.refresh_from_db()

    session = participant.match.game_session
    next_round = None
    can_continue_timed_round = (
        result != "timeout"
        and round_instance.mode == "timed_trivia"
        and round_instance.order + 1 >= len(session.modes)
        and now < round_instance.deadline
    )
    if can_continue_timed_round:
        next_deadline = round_instance.deadline
        if result == "wrong":
            next_deadline -= timedelta(seconds=MODE_RULES["timed_trivia"]["wrong_time_penalty"])
        if next_deadline > now:
            next_round = create_round(session, participant.match, "timed_trivia", round_instance.order + 1, next_deadline)
    elif round_instance.order + 1 < len(session.modes):
        next_round = create_round(session, participant.match, session.modes[round_instance.order + 1], round_instance.order + 1)

    if next_round is None:
        session.status = "finished"
        session.finished_at = now
        session.save(update_fields=["status", "finished_at", "updated_at"] if hasattr(session, "updated_at") else ["status", "finished_at"])
        participant.match.status = "finished"
        participant.match.finished_at = now
        participant.match.save(update_fields=["status", "finished_at"])
    return next_round


def _evaluate_round(round_instance: Round, answer, now):
    mode = round_instance.mode
    rules = MODE_RULES[mode]
    question = round_instance.question
    answer_data = question.payload.answer_data or {}
    state = round_instance.private_state or {}
    language = round_instance.match.language

    if mode == "hangman":
        action = answer.get("action") if isinstance(answer, dict) else "letter"
        if action == "hint":
            if state.get("hint_count", 0) >= rules["max_hints"]:
                raise ValidationError({"answer": "İpucu hakkı kalmadı."})
            state["hint_count"] = state.get("hint_count", 0) + 1
            return None, 0, state
        letter = _answer_value(answer, "letter")
        normalized_letter = normalize_answer(letter, language)
        if len(normalized_letter) != 1:
            raise ValidationError({"answer": "Çöp adam için tek harf gönderilmelidir."})
        guessed = set(state.get("guessed_letters", []))
        wrong_letters = set(state.get("wrong_letters", []))
        canonical = normalize_answer(answer_data.get("canonical", ""), language)
        if normalized_letter in guessed or normalized_letter in wrong_letters:
            raise ValidationError({"answer": "Bu harf daha önce denendi."})
        if normalized_letter in set(canonical):
            guessed.add(normalized_letter)
            state["guessed_letters"] = sorted(guessed)
            if set(character for character in canonical if character.isalpha()).issubset(guessed):
                remaining = _remaining_seconds(round_instance, now)
                points = max(0, rules["base_points"] - len(wrong_letters) * rules["wrong_letter_penalty"] - state.get("hint_count", 0) * rules["hint_penalty"])
                return "correct", points + remaining // rules["time_bonus_divisor"], state
        else:
            wrong_letters.add(normalized_letter)
            state["wrong_letters"] = sorted(wrong_letters)
            if len(wrong_letters) >= rules["max_wrong_letters"]:
                return "wrong", 0, state
        return None, 0, state

    if mode == "career_path":
        state["attempts_used"] = state.get("attempts_used", 0) + 1
        accepted = answer_data.get("accepted_answers", {}).get(language, [])
        if is_accepted_answer(_answer_value(answer, "text"), accepted, language):
            elapsed = max(0, int((now - round_instance.created_at).total_seconds()))
            revealed_extra = max(0, min(5, elapsed // rules["entry_reveal_interval"]))
            points = max(0, rules["base_points"] - revealed_extra * rules["revealed_entry_penalty"] - (state["attempts_used"] - 1) * rules["wrong_attempt_penalty"])
            return "correct", points + min(rules["max_time_bonus"], _remaining_seconds(round_instance, now) // rules["time_bonus_divisor"]), state
        if state["attempts_used"] >= rules["max_attempts"]:
            return "wrong", 0, state
        return None, 0, state

    if mode == "timed_trivia":
        if isinstance(answer, dict) and answer.get("action") == "skip":
            return "skipped", 0, state
        selected = _answer_value(answer, "choice_index")
        if selected is None:
            raise ValidationError({"answer": "Şık seçimi zorunludur."})
        try:
            selected = int(selected)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"answer": "Şık seçimi geçersiz."}) from exc
        response_seconds = max(0, int((now - round_instance.created_at).total_seconds()))
        bonus = max(0, rules["time_bonus_base"] - response_seconds // rules["time_bonus_divisor"])
        multiplier = rules["difficulty_multiplier"][question.difficulty]
        points = math.floor(10 * multiplier + 0.5) + bonus if selected == int(answer_data.get("correct_index", -1)) else 0
        return ("correct" if points else "wrong"), points, state

    if mode == "historical_score":
        if not isinstance(answer, dict) or "home" not in answer or "away" not in answer:
            raise ValidationError({"answer": "Ev ve deplasman skoru zorunludur."})
        try:
            home = int(answer["home"])
            away = int(answer["away"])
        except (TypeError, ValueError) as exc:
            raise ValidationError({"answer": "Skor alanları sayı olmalıdır."}) from exc
        exact = home == int(answer_data["regulation_home_goals"]) and away == int(answer_data["regulation_away_goals"])
        final_result = answer_data.get("final_result")
        result_value = "draw" if home == away else "home" if home > away else "away"
        if exact:
            return "correct", rules["exact_points"], state
        if result_value == final_result:
            return "correct", rules["result_only_points"], state
        return "wrong", 0, state

    if mode == "missing_lineup":
        state["attempts_used"] = state.get("attempts_used", 0) + 1
        hidden_answers = answer_data.get("hidden_answers", {}).get(language, [])
        accepted_groups = hidden_answers or [answer_data.get("accepted_answers", {}).get(language, [])]
        hidden_count = int(question.payload.public_payload.get("hidden_count", len(accepted_groups) or 1))
        found_indices = set(state.get("found_indices", []))
        submitted = _answer_value(answer, "text")
        matched_index = next(
            (
                index
                for index, accepted in enumerate(accepted_groups)
                if index not in found_indices and is_accepted_answer(submitted, accepted, language)
            ),
            None,
        )
        if matched_index is not None:
            found_indices.add(matched_index)
            state["found_indices"] = sorted(found_indices)
            if len(found_indices) >= hidden_count:
                points = len(found_indices) * rules["points_per_player"] + min(
                    rules["time_bonus_cap"], _remaining_seconds(round_instance, now) // rules["time_bonus_divisor"]
                )
                return "correct", points, state
        if state["attempts_used"] >= rules["max_attempts"]:
            return "wrong", len(found_indices) * rules["points_per_player"], state
        return None, 0, state

    raise ValidationError({"mode": f"Desteklenmeyen oyun modu: {mode}."})


@transaction.atomic
def submit_practice_answer(session_id, participant_id, round_id, answer):
    participant = MatchParticipant.objects.select_for_update().select_related("match", "match__game_session").get(id=participant_id)
    round_instance = (
        Round.objects.select_for_update()
        .select_related("question", "match", "match__game_session")
        .select_for_update(of=("self",))
        .get(id=round_id, match=participant.match)
    )
    if str(participant.match.game_session_id) != str(session_id):
        raise ValidationError({"session": "Tur bu pratik oturumuna ait değil."})
    if round_instance.status != "active":
        raise PracticeRoundConflict({"round": "Bu tur artık aktif değil."})
    now = timezone.now()
    if now >= round_instance.deadline:
        round_instance.private_state = round_instance.private_state or {}
        next_round = _final_answer(round_instance, participant, {"action": "timeout"}, "timeout", 0, now)
        return round_instance, participant, next_round

    result, points, state = _evaluate_round(round_instance, answer, now)
    round_instance.private_state = state
    if result is None:
        round_instance.save(update_fields=["private_state"])
        return round_instance, participant, None
    next_round = _final_answer(round_instance, participant, answer, result, points, now)
    return round_instance, participant, next_round
