from apps.quiz.management.commands.prepare_question_bank import (
    _build_definitions,
    _build_hangman_definitions,
    _lineup_candidate,
)


def test_build_definitions_creates_score_hangman_and_trivia_candidates():
    matches = {
        "matches": [
            {
                "date": "2023-08-11",
                "home": "Burnley",
                "away": "Manchester City",
                "home_goals": 0,
                "away_goals": 3,
                "competition": "English Premier League 2023/24",
            },
            {
                "date": "2023-08-12",
                "home": "Arsenal",
                "away": "Nottingham Forest",
                "home_goals": 2,
                "away_goals": 1,
                "competition": "English Premier League 2023/24",
            },
            {
                "date": "2023-08-13",
                "home": "Chelsea",
                "away": "Liverpool",
                "home_goals": 1,
                "away_goals": 0,
                "competition": "English Premier League 2023/24",
            },
            {
                "date": "2023-08-14",
                "home": "Everton",
                "away": "Fulham",
                "home_goals": 2,
                "away_goals": 0,
                "competition": "English Premier League 2023/24",
            },
        ]
    }

    definitions = _build_definitions(matches, score_limit=2, trivia_limit=2)
    modes = [definition[0]["mode"] for definition in definitions]

    assert modes.count("historical_score") == 2
    assert modes.count("timed_trivia") == 2
    assert all(definition[0]["mode"] != "published" for definition in definitions)
    assert all("answer_data" in definition[0] for definition in definitions)


def test_hangman_definitions_use_footballers_from_wikidata():
    definitions = _build_hangman_definitions(
        [
            {"player_id": "Q1", "player": "Ada Player", "player_tr": "Ada Oyuncu"},
            {"player_id": "Q2", "player": "Bora Player", "player_tr": "Bora Oyuncu"},
        ],
        limit=2,
    )

    assert [definition[0]["mode"] for definition in definitions] == ["hangman", "hangman"]
    assert all(definition[0]["public_payload"]["category"] == "footballer" for definition in definitions)
    assert definitions[0][0]["answer_data"]["canonical"] == "Ada Player"


def test_lineup_candidate_hides_one_starter_and_infers_rows():
    starters = [
        ("Goalkeeper", "Keeper"),
        ("Left Back", "Left back"),
        ("Right Back", "Right back"),
        ("Center Back", "Center back 1"),
        ("Center Back", "Center back 2"),
        ("Left Midfield", "Left midfield"),
        ("Center Midfield", "Center midfield"),
        ("Right Midfield", "Right midfield"),
        ("Left Wing", "Left wing"),
        ("Right Wing", "Right wing"),
        ("Center Forward", "Forward"),
    ]
    lineup = [
        {
            "player_name": name,
            "player_nickname": None,
            "positions": [{"position": position, "start_reason": "Starting XI"}],
        }
        for position, name in starters
    ]

    candidate = _lineup_candidate(
        {"match_id": 1, "match_date": "2018-06-16"},
        {"team_id": 2, "team_name": "Test FC", "lineup": lineup},
    )

    assert candidate is not None
    assert candidate["formation"] == "4-3-3"
    assert len(candidate["lineup"]) == 11
    assert sum(1 for slot in candidate["lineup"] if slot.get("hidden")) == 1
    assert candidate["answer"] not in {
        slot.get("name") for slot in candidate["lineup"] if not slot.get("hidden")
    }
