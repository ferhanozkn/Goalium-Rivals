MODE_CHOICES = (
    ("hangman", "Hangman"),
    ("career_path", "Career path"),
    ("timed_trivia", "Timed trivia"),
    ("historical_score", "Historical score"),
    ("missing_lineup", "Missing lineup"),
)

LANGUAGE_CHOICES = (("tr", "Türkçe"), ("en", "English"))

DIFFICULTY_CHOICES = (("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard"))

QUESTION_STATUS_CHOICES = (
    ("draft", "Draft"),
    ("in_review", "In review"),
    ("approved", "Approved"),
    ("published", "Published"),
    ("retired", "Retired"),
)

SOURCE_LICENSE_STATUS_CHOICES = (
    ("pending", "Pending"),
    ("verified", "Verified"),
    ("blocked", "Blocked"),
)
