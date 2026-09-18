import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.content.models import Question, QuestionPayload, QuestionTranslation, SourceReference


OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/football.json/master/2023-24/en.1.json"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
STATSBOMB_MATCHES_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/43/3.json"
STATSBOMB_LINEUP_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/lineups/{match_id}.json"


class RemoteDataError(CommandError):
    pass


@dataclass(frozen=True)
class SourceInfo:
    provider: str
    url: str
    license_name: str
    license_status: str
    notes: str


OPENFOOTBALL_SOURCE = SourceInfo(
    provider="openfootball",
    url=OPENFOOTBALL_URL,
    license_name="CC0",
    license_status="verified",
    notes="2023/24 English Premier League JSON; source repository and license are CC0.",
)
WIKIDATA_SOURCE = SourceInfo(
    provider="Wikidata",
    url=WIKIDATA_ENDPOINT,
    license_name="CC0",
    license_status="verified",
    notes="SPARQL result generated from Wikidata structured data; candidate facts require editorial review.",
)
STATSBOMB_SOURCE = SourceInfo(
    provider="StatsBomb Open Data",
    url=STATSBOMB_MATCHES_URL,
    license_name="StatsBomb Open Data - rights review pending",
    license_status="pending",
    notes="Research/analysis dataset; publication rights and attribution requirements are not cleared for production.",
)


class RemoteFetcher:
    user_agent = "Goalium-Rivals-content-import/1.0 (https://github.com/ferhanozkn/Goalium-Rivals)"

    def get_json(self, url: str) -> object:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=35) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RemoteDataError(f"Uzak veri alınamadı: {url} ({exc})") from exc


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:72] or "record"


def _stable_index(value: str, length: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % length


def _year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d{4})", value)
    return int(match.group(1)) if match else None


def _team_label(value: str) -> str:
    return re.sub(r"\s+(FC|AFC)$", "", value).strip()


def _source(info: SourceInfo, *, url: str | None = None) -> SourceReference:
    source, _ = SourceReference.objects.get_or_create(
        provider=info.provider,
        url=url or info.url,
        defaults={
            "license_name": info.license_name,
            "license_status": info.license_status,
            "notes": info.notes,
        },
    )
    return source


def _question_definition(
    *,
    seed_key: str,
    mode: str,
    difficulty: str,
    public_payload: dict,
    answer_data: dict,
    tr: dict,
    en: dict,
) -> dict:
    return {
        "seed_key": seed_key,
        "mode": mode,
        "difficulty": difficulty,
        "public_payload": public_payload,
        "answer_data": answer_data,
        "translations": {"tr": tr, "en": en},
    }


def _save_question(definition: dict, sources: list[SourceReference]) -> tuple[bool, bool]:
    question, created = Question.objects.get_or_create(
        seed_key=definition["seed_key"],
        defaults={
            "mode": definition["mode"],
            "difficulty": definition["difficulty"],
            "status": "draft",
        },
    )
    if not created and question.status != "draft":
        return False, False

    QuestionPayload.objects.update_or_create(
        question=question,
        defaults={
            "public_payload": definition["public_payload"],
            "answer_data": definition["answer_data"],
        },
    )
    for language, translation in definition["translations"].items():
        QuestionTranslation.objects.update_or_create(
            question=question,
            language=language,
            defaults={
                "prompt": translation["prompt"],
                "choices": translation.get("choices", []),
                "hints": translation.get("hints", []),
                "public_data": translation.get("public_data", {}),
            },
        )
    question.source_references.set(sources)
    return True, created


def _fetch_matches(fetcher: RemoteFetcher) -> dict:
    payload = fetcher.get_json(OPENFOOTBALL_URL)
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise RemoteDataError("openfootball yanıtı beklenen matches listesini içermiyor.")
    matches = []
    for raw in payload["matches"]:
        score = raw.get("score") if isinstance(raw, dict) else None
        full_time = score.get("ft") if isinstance(score, dict) else None
        if not isinstance(full_time, list) or len(full_time) != 2 or not all(isinstance(item, int) for item in full_time):
            continue
        if not raw.get("date") or not raw.get("team1") or not raw.get("team2"):
            continue
        matches.append(
            {
                "date": raw["date"],
                "home": _team_label(raw["team1"]),
                "away": _team_label(raw["team2"]),
                "home_goals": full_time[0],
                "away_goals": full_time[1],
                "competition": payload.get("name", "English Premier League"),
            }
        )
    if not matches:
        raise RemoteDataError("openfootball yanıtında kullanılabilir tamamlanmış maç bulunamadı.")
    return {"name": payload.get("name", "English Premier League"), "matches": matches}


def _fetch_career_rows(fetcher: RemoteFetcher) -> list[dict]:
    query = """
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX p: <http://www.wikidata.org/prop/>
    PREFIX ps: <http://www.wikidata.org/prop/statement/>
    PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?player ?playerLabel ?playerLabelTr ?team ?teamLabel ?teamLabelTr ?start ?end WHERE {
      ?player wdt:P106 wd:Q937857 ; p:P54 ?membership.
      ?membership ps:P54 ?team.
      OPTIONAL { ?membership pq:P580 ?start. }
      OPTIONAL { ?membership pq:P582 ?end. }
      FILTER(BOUND(?start) || BOUND(?end))
      ?player rdfs:label ?playerLabel.
      FILTER(LANG(?playerLabel) = "en")
      OPTIONAL {
        ?player rdfs:label ?playerLabelTr.
        FILTER(LANG(?playerLabelTr) = "tr")
      }
      ?team rdfs:label ?teamLabel.
      FILTER(LANG(?teamLabel) = "en")
      OPTIONAL {
        ?team rdfs:label ?teamLabelTr.
        FILTER(LANG(?teamLabelTr) = "tr")
      }
    }
    LIMIT 600
    """
    query_url = f"{WIKIDATA_ENDPOINT}?{urlencode({'query': query, 'format': 'json'})}"
    payload = fetcher.get_json(query_url)
    bindings = payload.get("results", {}).get("bindings", []) if isinstance(payload, dict) else []
    if not isinstance(bindings, list):
        return []
    rows = []
    for binding in bindings:
        player = binding.get("player", {}).get("value")
        team = binding.get("team", {}).get("value")
        player_label = binding.get("playerLabel", {}).get("value")
        team_label = binding.get("teamLabel", {}).get("value")
        if not player or not team or not player_label or not team_label:
            continue
        rows.append(
            {
                "player_id": player.rsplit("/", 1)[-1],
                "player": player_label,
                "player_tr": binding.get("playerLabelTr", {}).get("value", player_label),
                "team_id": team.rsplit("/", 1)[-1],
                "team": team_label,
                "team_tr": binding.get("teamLabelTr", {}).get("value", team_label),
                "start": _year(binding.get("start", {}).get("value")),
                "end": _year(binding.get("end", {}).get("value")),
            }
        )
    return rows


def _fetch_lineup_candidates(fetcher: RemoteFetcher, limit: int) -> list[dict]:
    matches = fetcher.get_json(STATSBOMB_MATCHES_URL)
    if not isinstance(matches, list):
        return []
    candidates = []
    for match in matches:
        if len(candidates) >= limit:
            break
        match_id = match.get("match_id")
        if not match_id or _year(match.get("match_date")) is None or _year(match.get("match_date")) < 2010:
            continue
        lineup_url = STATSBOMB_LINEUP_URL.format(match_id=match_id)
        try:
            lineups = fetcher.get_json(lineup_url)
        except RemoteDataError:
            continue
        if not isinstance(lineups, list):
            continue
        for team_lineup in lineups:
            candidate = _lineup_candidate(match, team_lineup)
            if candidate:
                candidate["lineup_url"] = lineup_url
                candidates.append(candidate)
                if len(candidates) >= limit:
                    break
    return candidates


def _lineup_candidate(match: dict, team_lineup: dict) -> dict | None:
    starters = []
    for player in team_lineup.get("lineup", []):
        positions = player.get("positions") or []
        starting_position = next(
            (position for position in positions if position.get("start_reason") == "Starting XI"),
            None,
        )
        if starting_position:
            starters.append(
                {
                    "name": player.get("player_nickname") or player.get("player_name"),
                    "position": starting_position.get("position", ""),
                }
            )
    if len(starters) != 11 or not all(player["name"] for player in starters):
        return None

    def group(player: dict) -> str:
        position = player["position"].lower()
        if "goalkeeper" in position:
            return "gk"
        if "back" in position:
            return "def"
        if "wing" in position or "forward" in position:
            return "fwd"
        return "mid"

    grouped = {key: [player for player in starters if group(player) == key] for key in ("gk", "def", "mid", "fwd")}
    if len(grouped["gk"]) != 1 or len(grouped["def"]) + len(grouped["mid"]) + len(grouped["fwd"]) != 10:
        return None
    formation = f"{len(grouped['def'])}-{len(grouped['mid'])}-{len(grouped['fwd'])}"
    if any(width < 1 or width > 5 for width in map(int, formation.split("-"))):
        return None
    ordered = grouped["gk"] + grouped["def"] + grouped["mid"] + grouped["fwd"]
    hidden_index = _stable_index(f"{match['match_id']}:{team_lineup.get('team_id')}", 10) + 1
    hidden_player = ordered[hidden_index]
    public_lineup = [
        {"hidden": True} if index == hidden_index else {"name": player["name"]}
        for index, player in enumerate(ordered)
    ]
    team = team_lineup.get("team_name", "")
    return {
        "match_id": match["match_id"],
        "match_date": match.get("match_date"),
        "team_id": team_lineup.get("team_id"),
        "team": team,
        "formation": formation,
        "lineup": public_lineup,
        "answer": hidden_player["name"],
    }


def _build_definitions(matches: dict, score_limit: int, trivia_limit: int) -> list[tuple[dict, list[SourceInfo]]]:
    rows = matches["matches"]
    definitions: list[tuple[dict, list[SourceInfo]]] = []
    for match in rows[:score_limit]:
        seed = f"pilot:historical-score:openfootball:{_slug(match['date'])}:{_slug(match['home'])}:{_slug(match['away'])}"
        score = f"{match['home_goals']}-{match['away_goals']}"
        definition = _question_definition(
            seed_key=seed[:120],
            mode="historical_score",
            difficulty="medium",
            public_payload={
                "home_team": {"tr": match["home"], "en": match["home"]},
                "away_team": {"tr": match["away"], "en": match["away"]},
                "competition": match["competition"],
                "played_on": match["date"],
                "score_is_regulation": True,
            },
            answer_data={"regulation_home_goals": match["home_goals"], "regulation_away_goals": match["away_goals"]},
            tr={"prompt": f"{match['date']} tarihinde {match['home']} ile {match['away']} arasındaki maçın skoru neydi?", "hints": ["Premier League 2023/24", "Normal süre skoru"]},
            en={"prompt": f"What was the score of {match['home']} vs {match['away']} on {match['date']}?", "hints": ["Premier League 2023/24", "Regulation score"]},
        )
        definitions.append((definition, [OPENFOOTBALL_SOURCE]))

    all_teams = sorted({team for match in rows for team in (match["home"], match["away"])})
    trivia_count = 0
    for match in rows:
        if trivia_count >= trivia_limit or match["home_goals"] == match["away_goals"]:
            continue
        winner = match["home"] if match["home_goals"] > match["away_goals"] else match["away"]
        alternatives = [team for team in all_teams if team not in {winner, match["home"], match["away"]}]
        if len(alternatives) < 3:
            continue
        choices = [winner, *alternatives[:3]]
        shift = _stable_index(f"trivia:{match['date']}:{match['home']}:{match['away']}", len(choices))
        choices = choices[shift:] + choices[:shift]
        definition = _question_definition(
            seed_key=f"pilot:timed-trivia:openfootball:{_slug(match['date'])}:{_slug(match['home'])}:{_slug(match['away'])}"[:120],
            mode="timed_trivia",
            difficulty="easy",
            public_payload={"category": "match_winner", "competition": match["competition"], "played_on": match["date"]},
            answer_data={"correct_index": choices.index(winner)},
            tr={"prompt": f"{match['date']} tarihinde {match['home']} ile {match['away']} maçını hangi takım kazandı?", "choices": choices},
            en={"prompt": f"Which team won {match['home']} vs {match['away']} on {match['date']}?", "choices": choices},
        )
        definitions.append((definition, [OPENFOOTBALL_SOURCE]))
        trivia_count += 1
    return definitions


def _build_hangman_definitions(rows: list[dict], limit: int) -> list[tuple[dict, list[SourceInfo]]]:
    grouped: dict[str, dict] = {}
    for row in rows:
        grouped.setdefault(row["player_id"], row)

    definitions = []
    for player_id, player in sorted(grouped.items()):
        answer = player["player"]
        word_length = len(re.sub(r"[^A-Za-zÀ-ÿ]", "", answer))
        definition = _question_definition(
            seed_key=f"pilot:hangman:wikidata:{_slug(player_id)}"[:120],
            mode="hangman",
            difficulty="medium",
            public_payload={"category": "footballer", "word_length": word_length},
            answer_data={
                "canonical": answer,
                "accepted_answers": {"tr": [player["player_tr"], answer], "en": [answer]},
            },
            tr={"prompt": "Bu futbolcunun adını harfleri açarak bulun.", "hints": ["Futbolcu", f"Harf sayısı: {word_length}"]},
            en={"prompt": "Reveal the name of this footballer letter by letter.", "hints": ["Footballer", f"Letter count: {word_length}"]},
        )
        definitions.append((definition, [WIKIDATA_SOURCE]))
        if len(definitions) >= limit:
            break
    return definitions


def _remove_legacy_hangman_drafts() -> int:
    legacy = Question.objects.filter(status="draft", seed_key__startswith="pilot:hangman:openfootball:")
    count = legacy.count()
    legacy.delete()
    return count


def _build_career_definitions(rows: list[dict], limit: int) -> list[tuple[dict, list[SourceInfo]]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["player_id"]].append(row)
    definitions = []
    for player_id, entries in sorted(grouped.items(), key=lambda item: item[0]):
        unique_entries = {(entry["team_id"], entry["team"], entry["team_tr"], entry["start"], entry["end"]): entry for entry in entries}
        entries = sorted(unique_entries.values(), key=lambda entry: (entry["start"] or 9999, entry["team"]))
        if len(entries) < 3 or not all(entry["start"] or entry["end"] for entry in entries):
            continue
        entries = entries[:6]
        tr_entries = [{"club": entry["team_tr"], "years": f"{entry['start'] or '?'}–{entry['end'] or '?'}"} for entry in entries]
        en_entries = [{"club": entry["team"], "years": f"{entry['start'] or '?'}–{entry['end'] or '?'}"} for entry in entries]
        player = entries[0]
        definition = _question_definition(
            seed_key=f"pilot:career-path:wikidata:{_slug(player_id)}"[:120],
            mode="career_path",
            difficulty="medium",
            public_payload={"format": "career_path"},
            answer_data={"canonical": player["player"], "accepted_answers": {"tr": [player["player_tr"], player["player"]], "en": [player["player"]]}},
            tr={"prompt": "Bu kronolojik kulüp yoluna göre oyuncuyu bulun.", "hints": ["Senior kulüp geçmişi", "Veri kaynağı: Wikidata"], "public_data": {"entries": tr_entries}},
            en={"prompt": "Identify the player from this chronological club path.", "hints": ["Senior club history", "Data source: Wikidata"], "public_data": {"entries": en_entries}},
        )
        definitions.append((definition, [WIKIDATA_SOURCE]))
        if len(definitions) >= limit:
            break
    return definitions


def _build_lineup_definitions(candidates: list[dict]) -> list[tuple[dict, list[SourceInfo]]]:
    definitions = []
    for candidate in candidates:
        seed = f"pilot:missing-lineup:statsbomb:{candidate['match_id']}:{candidate['team_id']}"
        lineup_source = SourceInfo(
            provider=STATSBOMB_SOURCE.provider,
            url=candidate["lineup_url"],
            license_name=STATSBOMB_SOURCE.license_name,
            license_status=STATSBOMB_SOURCE.license_status,
            notes=STATSBOMB_SOURCE.notes,
        )
        definition = _question_definition(
            seed_key=seed[:120],
            mode="missing_lineup",
            difficulty="medium",
            public_payload={
                "hidden_count": 1,
                "team": {"tr": candidate["team"], "en": candidate["team"]},
                "formation": candidate["formation"],
                "lineup": candidate["lineup"],
                "match_date": candidate["match_date"],
            },
            answer_data={"accepted_answers": {"tr": [candidate["answer"]], "en": [candidate["answer"]]}},
            tr={"prompt": f"{candidate['match_date']} tarihli {candidate['team']} ilk 11'indeki eksik oyuncuyu bulun.", "hints": ["Kaynak kadro verisi editör incelemesinde."]},
            en={"prompt": f"Find the missing player in {candidate['team']}'s starting XI on {candidate['match_date']}.", "hints": ["The lineup source is under editorial review."]},
        )
        definitions.append((definition, [
            _source(STATSBOMB_SOURCE),
            _source(lineup_source),
        ]))
    return definitions


class Command(BaseCommand):
    help = "Ücretsiz kaynaklardan pilot soru adaylarını çeker ve draft olarak PostgreSQL'e hazırlar."

    def add_arguments(self, parser):
        parser.add_argument("--score-limit", type=int, default=20)
        parser.add_argument("--hangman-limit", type=int, default=10)
        parser.add_argument("--trivia-limit", type=int, default=20)
        parser.add_argument("--career-limit", type=int, default=10)
        parser.add_argument("--lineup-limit", type=int, default=5)
        parser.add_argument("--skip-career", action="store_true")
        parser.add_argument("--skip-lineup", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if any(options[name] < 0 for name in ("score_limit", "hangman_limit", "trivia_limit", "career_limit", "lineup_limit")):
            raise CommandError("Limit değerleri negatif olamaz.")

        fetcher = RemoteFetcher()
        try:
            matches = _fetch_matches(fetcher)
        except RemoteDataError as exc:
            raise CommandError(str(exc)) from exc

        definitions = _build_definitions(matches, options["score_limit"], options["trivia_limit"])
        career_rows = []
        if (not options["skip_career"] and options["career_limit"]) or options["hangman_limit"]:
            try:
                career_rows = _fetch_career_rows(fetcher)
            except RemoteDataError as exc:
                self.stdout.write(self.style.WARNING(f"Wikidata adayları atlandı: {exc}"))
        if options["hangman_limit"]:
            definitions.extend(_build_hangman_definitions(career_rows, options["hangman_limit"]))
        if not options["skip_career"] and options["career_limit"]:
            definitions.extend(_build_career_definitions(career_rows, options["career_limit"]))
        if not options["skip_lineup"] and options["lineup_limit"]:
            try:
                definitions.extend(_build_lineup_definitions(_fetch_lineup_candidates(fetcher, options["lineup_limit"])))
            except RemoteDataError as exc:
                self.stdout.write(self.style.WARNING(f"İlk 11 adayları atlandı: {exc}"))

        sources = {
            (info.provider, info.url): _source(info)
            for info in (OPENFOOTBALL_SOURCE, WIKIDATA_SOURCE, STATSBOMB_SOURCE)
        }
        removed_legacy = _remove_legacy_hangman_drafts()
        created = 0
        refreshed = 0
        skipped = 0
        for definition, source_infos in definitions:
            source_refs = []
            for info in source_infos:
                key = (info.provider, info.url)
                source_refs.append(sources.get(key) or _source(info))
            saved, was_created = _save_question(definition, source_refs)
            if saved:
                created += int(was_created)
                refreshed += int(not was_created)
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Pilot soru hazırlığı tamamlandı: {created} yeni draft, {refreshed} mevcut draft güncellendi, "
                f"{skipped} yayın akışındaki kayıt atlandı; "
                f"{removed_legacy} eski takım-adı çöp adam draftı kaldırıldı; kaynakta {len(matches['matches'])} maç işlendi."
            )
        )
