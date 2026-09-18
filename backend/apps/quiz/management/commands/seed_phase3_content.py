from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.content.models import Question, QuestionPayload, QuestionTranslation, SourceReference


QUESTIONS = [
    {
        "seed_key": "phase3:hangman:iniesta",
        "mode": "hangman",
        "difficulty": "medium",
        "source": ("Wikidata", "https://www.wikidata.org/wiki/Q160530"),
        "public_payload": {"category": "footballer", "word_length": 13},
        "answer_data": {
            "canonical": "Andrés Iniesta",
            "accepted_answers": {"tr": ["Andrés Iniesta", "Andres Iniesta", "Iniesta"], "en": ["Andrés Iniesta", "Andres Iniesta", "Iniesta"]},
        },
        "translations": {
            "tr": {
                "prompt": "Bu futbolcunun adını harfleri açarak bulun.",
                "hints": ["Futbolcu", "İspanya millî takımının eski oyuncusu"],
                "public_data": {"category": "Futbolcu"},
            },
            "en": {
                "prompt": "Reveal the name of this footballer letter by letter.",
                "hints": ["Footballer", "Former Spain international"],
                "public_data": {"category": "Footballer"},
            },
        },
    },
    {
        "seed_key": "phase3:career:iniesta",
        "mode": "career_path",
        "difficulty": "medium",
        "source": ("FC Barcelona", "https://players.fcbarcelona.com/en/player/405-iniesta-andres-iniesta"),
        "public_payload": {"format": "career_path"},
        "answer_data": {
            "canonical": "Andrés Iniesta",
            "accepted_answers": {"tr": ["Andrés Iniesta", "Andres Iniesta", "Iniesta"], "en": ["Andrés Iniesta", "Andres Iniesta", "Iniesta"]},
        },
        "translations": {
            "tr": {
                "prompt": "Oyuncuyu kulüp geçmişinden bulun.",
                "hints": ["İlk kulüp Barcelona"],
                "public_data": {"entries": [{"club": "Barcelona", "years": "2002–2018"}, {"club": "Vissel Kobe", "years": "2018–2023"}, {"club": "Emirates Club", "years": "2023–2024"}]},
            },
            "en": {
                "prompt": "Identify the player from this club path.",
                "hints": ["The first club is Barcelona"],
                "public_data": {"entries": [{"club": "Barcelona", "years": "2002–2018"}, {"club": "Vissel Kobe", "years": "2018–2023"}, {"club": "Emirates Club", "years": "2023–2024"}]},
            },
        },
    },
    {
        "seed_key": "phase3:trivia:iniesta-2010-final",
        "mode": "timed_trivia",
        "difficulty": "medium",
        "source": ("FIFA", "https://www.fifa.com/es/articles/asi-fue-la-final-andres-iniesta-en-la-copa-mundial-fifa-sudafrica-2010"),
        "public_payload": {},
        "answer_data": {"correct_index": 0},
        "translations": {
            "tr": {
                "prompt": "2010 FIFA Dünya Kupası finalinde İspanya adına uzatmalarda gol atan oyuncu kimdir?",
                "choices": ["Andrés Iniesta", "Xavi Hernández", "David Villa", "Carles Puyol"],
                "public_data": {},
            },
            "en": {
                "prompt": "Who scored Spain's extra-time goal in the 2010 FIFA World Cup final?",
                "choices": ["Andrés Iniesta", "Xavi Hernández", "David Villa", "Carles Puyol"],
                "public_data": {},
            },
        },
    },
    {
        "seed_key": "phase3:trivia:world-cup-2018-winner",
        "mode": "timed_trivia",
        "difficulty": "easy",
        "source": ("FIFA", "https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/worldcupathome-france-croatia-russia-2018-3072767"),
        "additional_sources": [("DFB", "https://datencenter.dfb.de/datencenter/weltmeisterschaft/2018-in-russland/finale/sieger-halbfinale-1-sieger-halbfinale-2-2248356")],
        "public_payload": {},
        "answer_data": {"correct_index": 0},
        "translations": {
            "tr": {
                "prompt": "2018 FIFA Dünya Kupası'nı hangi ülke kazandı?",
                "choices": ["Fransa", "Hırvatistan", "Belçika", "İngiltere"],
                "public_data": {},
            },
            "en": {
                "prompt": "Which country won the 2018 FIFA World Cup?",
                "choices": ["France", "Croatia", "Belgium", "England"],
                "public_data": {},
            },
        },
    },
    {
        "seed_key": "phase3:historical-score:2010-final",
        "mode": "historical_score",
        "difficulty": "medium",
        "source": ("FIFA", "https://www.fifa.com/es/articles/asi-fue-la-final-andres-iniesta-en-la-copa-mundial-fifa-sudafrica-2010"),
        "public_payload": {"home_team": {"tr": "Hollanda", "en": "Netherlands"}, "away_team": {"tr": "İspanya", "en": "Spain"}, "played_on": "2010-07-11"},
        "answer_data": {"regulation_home_goals": 0, "regulation_away_goals": 0, "final_result": "away"},
        "translations": {
            "tr": {"prompt": "11 Temmuz 2010 FIFA Dünya Kupası finalinde Hollanda–İspanya maçının normal süre skoru neydi?", "hints": ["Maç uzatmaya gitti."], "public_data": {}},
            "en": {"prompt": "What was the score after 90 minutes in the Netherlands–Spain final of the 2010 FIFA World Cup?", "hints": ["The match went to extra time."], "public_data": {}},
        },
    },
    {
        "seed_key": "phase3:missing-lineup:2018-final",
        "mode": "missing_lineup",
        "difficulty": "easy",
        "source": ("FIFA", "https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/worldcupathome-france-croatia-russia-2018-3072767"),
        "public_payload": {
            "hidden_count": 1,
            "team": {"tr": "Fransa", "en": "France"},
            "formation": "4-2-3-1",
            "lineup": [
                "Hugo Lloris",
                "Lucas Hernandez", "Samuel Umtiti", "Raphaël Varane", "Benjamin Pavard",
                "Paul Pogba", "N'Golo Kanté",
                "Blaise Matuidi", "____", "Kylian Mbappé",
                "Olivier Giroud",
            ],
        },
        "answer_data": {"accepted_answers": {"tr": ["Antoine Griezmann", "Griezmann"], "en": ["Antoine Griezmann", "Griezmann"]}},
        "translations": {
            "tr": {
                "prompt": "2018 FIFA Dünya Kupası finalindeki Fransa ilk 11'inde eksik oyuncuyu bulun.",
                "hints": ["Forvet hattında oynadı."],
                "public_data": {},
            },
            "en": {
                "prompt": "Find the missing player in France's starting XI in the 2018 FIFA World Cup final.",
                "hints": ["He played in the forward line."],
                "public_data": {},
            },
        },
    },
]


class Command(BaseCommand):
    help = "Faz 3 için doğrulanmış iki dilli örnek soruları PostgreSQL'e ekler."

    @transaction.atomic
    def handle(self, *args, **options):
        Question.objects.filter(seed_key="phase3:hangman:offside").exclude(status="retired").update(
            status="retired",
            published_at=timezone.now(),
        )
        for definition in QUESTIONS:
            sources = []
            for provider, url in [definition["source"], *definition.get("additional_sources", [])]:
                source, _ = SourceReference.objects.get_or_create(
                    provider=provider,
                    url=url,
                    defaults={"license_name": "Reference-only source policy", "license_status": "verified"},
                )
                source.license_status = "verified"
                source.save(update_fields=["license_status", "updated_at"])
                sources.append(source)
            question, _ = Question.objects.update_or_create(
                seed_key=definition["seed_key"],
                defaults={"mode": definition["mode"], "difficulty": definition["difficulty"]},
            )
            QuestionPayload.objects.update_or_create(
                question=question,
                defaults={"public_payload": definition["public_payload"], "answer_data": definition["answer_data"]},
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
            question.validate_publishable()
            question.status = "published"
            question.published_at = question.published_at or timezone.now()
            question.save(update_fields=["status", "published_at", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"{len(QUESTIONS)} Faz 3 sorusu hazırlandı."))
