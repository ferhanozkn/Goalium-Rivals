import unicodedata


TURKISH_EQUIVALENTS = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"})


def locale_lower(value: str, language: str) -> str:
    if language == "tr":
        value = value.translate(str.maketrans({"I": "ı", "İ": "i"}))
    return value.lower()


def normalize_answer(value, language: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = locale_lower(text, language)
    cleaned = []
    for character in text:
        if unicodedata.category(character).startswith("P"):
            cleaned.append(" ")
        else:
            cleaned.append(character)
    text = "".join(cleaned)
    text = " ".join(text.split())
    return text.translate(TURKISH_EQUIVALENTS)


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[right_index - 1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def is_accepted_answer(value, accepted_answers: list[str], language: str) -> bool:
    normalized = normalize_answer(value, language)
    if not normalized:
        return False
    for accepted in accepted_answers:
        normalized_accepted = normalize_answer(accepted, language)
        if normalized == normalized_accepted:
            return True
        tolerance = 0 if len(normalized_accepted) <= 3 else 1 if len(normalized_accepted) <= 7 else 2
        if levenshtein_distance(normalized, normalized_accepted) <= tolerance:
            return True
    return False
