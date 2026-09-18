from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.content.models import (
    Competition,
    FootballMatch,
    LineupSlot,
    MatchLineup,
    Player,
    PlayerCareerEntry,
    Season,
    Team,
)
from apps.imports.models import ImportJob, ImportRecord


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: int = 0


class CatalogImporter:
    """Maps provider-neutral records into the PostgreSQL content catalog."""

    def run(self, job: ImportJob, records: list[dict]) -> ImportResult:
        result = ImportResult()
        job.status = "running"
        job.record_count = len(records)
        job.started_at = timezone.now()
        job.error_message = ""
        job.save(update_fields=["status", "record_count", "started_at", "error_message"])

        for raw_record in records:
            record_type = raw_record.get("record_type", "")
            external_id = str(raw_record.get("external_id", ""))
            import_record, _ = ImportRecord.objects.get_or_create(
                job=job,
                record_type=record_type,
                external_id=external_id,
                defaults={"raw_payload": raw_record},
            )
            if import_record.status == "imported":
                result.skipped += 1
                continue
            import_record.raw_payload = raw_record
            try:
                with transaction.atomic():
                    target = self._upsert(record_type, raw_record, job)
                    import_record.status = "imported"
                    import_record.target_model = target._meta.label
                    import_record.target_id = target.id
                    import_record.error_message = ""
                    import_record.save(
                        update_fields=[
                            "raw_payload",
                            "status",
                            "target_model",
                            "target_id",
                            "error_message",
                            "updated_at",
                        ]
                    )
                result.imported += 1
            except (KeyError, ValueError, TypeError, ObjectDoesNotExist) as exc:
                import_record.status = "error"
                import_record.error_message = str(exc)
                import_record.save(update_fields=["raw_payload", "status", "error_message", "updated_at"])
                result.errors += 1

        job.imported_count = result.imported
        job.skipped_count = result.skipped
        job.error_count = result.errors
        job.status = "failed" if result.errors else "completed"
        job.finished_at = timezone.now()
        if result.errors:
            job.error_message = "Bir veya daha fazla kayıt içe aktarılamadı."
        job.save(update_fields=["imported_count", "skipped_count", "error_count", "status", "finished_at", "error_message"])
        return result

    def _upsert(self, record_type: str, data: dict, job: ImportJob):
        if record_type == "competition":
            return Competition.objects.update_or_create(
                external_id=self._external_id(data),
                defaults=self._with_source(
                    job,
                    {
                        "name": data["name"],
                        "country_code": data.get("country_code", ""),
                        "kind": data.get("kind", "league"),
                    },
                ),
            )[0]
        if record_type == "season":
            competition = Competition.objects.get(external_id=data["competition_external_id"])
            return Season.objects.update_or_create(
                external_id=self._external_id(data),
                defaults={
                    "competition": competition,
                    "label": data["label"],
                    "start_year": int(data["start_year"]),
                    "end_year": int(data["end_year"]),
                },
            )[0]
        if record_type == "team":
            return Team.objects.update_or_create(
                external_id=self._external_id(data),
                defaults=self._with_source(job, {"name": data["name"], "country_code": data.get("country_code", "")}),
            )[0]
        if record_type == "player":
            return Player.objects.update_or_create(
                external_id=self._external_id(data),
                defaults=self._with_source(
                    job,
                    {
                        "name": data["name"],
                        "birth_date": data.get("birth_date"),
                        "nationality": data.get("nationality", ""),
                    },
                ),
            )[0]
        if record_type == "career_entry":
            player = Player.objects.get(external_id=data["player_external_id"])
            team = Team.objects.get(external_id=data["team_external_id"])
            return PlayerCareerEntry.objects.update_or_create(
                external_id=self._external_id(data),
                defaults={
                    "player": player,
                    "team": team,
                    "start_year": int(data["start_year"]),
                    "end_year": data.get("end_year"),
                    "transfer_type": data.get("transfer_type", ""),
                },
            )[0]
        if record_type == "match":
            competition = Competition.objects.get(external_id=data["competition_external_id"])
            season = Season.objects.get(external_id=data["season_external_id"])
            home_team = Team.objects.get(external_id=data["home_team_external_id"])
            away_team = Team.objects.get(external_id=data["away_team_external_id"])
            return FootballMatch.objects.update_or_create(
                external_id=self._external_id(data),
                defaults=self._with_source(
                    job,
                    {
                        "competition": competition,
                        "season": season,
                        "played_on": data["played_on"],
                        "home_team": home_team,
                        "away_team": away_team,
                        "regulation_home_goals": int(data["regulation_home_goals"]),
                        "regulation_away_goals": int(data["regulation_away_goals"]),
                        "final_home_goals": data.get("final_home_goals"),
                        "final_away_goals": data.get("final_away_goals"),
                        "went_extra_time": bool(data.get("went_extra_time", False)),
                        "went_to_penalties": bool(data.get("went_to_penalties", False)),
                    },
                ),
            )[0]
        if record_type == "lineup":
            football_match = FootballMatch.objects.get(external_id=data["match_external_id"])
            team = Team.objects.get(external_id=data["team_external_id"])
            lineup, _ = MatchLineup.objects.update_or_create(
                football_match=football_match,
                team=team,
                defaults={"formation": data.get("formation", "")},
            )
            for slot in data.get("slots", []):
                player = Player.objects.get(external_id=slot["player_external_id"])
                LineupSlot.objects.update_or_create(
                    lineup=lineup,
                    slot_order=int(slot["slot_order"]),
                    defaults={
                        "position": slot["position"],
                        "player": player,
                        "is_starter": bool(slot.get("is_starter", True)),
                    },
                )
            return lineup
        raise ValueError(f"Desteklenmeyen kayıt türü: {record_type}")

    @staticmethod
    def _external_id(data: dict) -> str:
        value = data.get("external_id")
        if not value:
            raise ValueError("external_id zorunludur.")
        return str(value)

    @staticmethod
    def _with_source(job: ImportJob, values: dict) -> dict:
        values["source_url"] = job.source_url
        values["source_license"] = job.license_name
        return values
