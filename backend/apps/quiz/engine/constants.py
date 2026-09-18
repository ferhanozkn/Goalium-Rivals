MODE_RULES = {
    "hangman": {
        "duration_seconds": 90,
        "max_wrong_letters": 6,
        "max_hints": 2,
        "base_points": 100,
        "wrong_letter_penalty": 10,
        "hint_penalty": 15,
        "time_bonus_divisor": 5,
    },
    "career_path": {
        "duration_seconds": 60,
        "max_attempts": 3,
        "base_points": 100,
        "revealed_entry_penalty": 15,
        "wrong_attempt_penalty": 10,
        "time_bonus_divisor": 10,
        "max_time_bonus": 10,
        "entry_reveal_interval": 10,
    },
    "timed_trivia": {
        "duration_seconds": 60,
        "wrong_time_penalty": 3,
        "time_bonus_base": 5,
        "time_bonus_divisor": 2,
        "difficulty_multiplier": {"easy": 1, "medium": 1.5, "hard": 2},
    },
    "historical_score": {
        "duration_seconds": 45,
        "exact_points": 30,
        "result_only_points": 15,
    },
    "missing_lineup": {
        "duration_seconds": 45,
        "max_attempts": 2,
        "points_per_player": 50,
        "time_bonus_cap": 20,
        "time_bonus_divisor": 5,
    },
}


def mode_duration(mode: str) -> int:
    return MODE_RULES[mode]["duration_seconds"]
