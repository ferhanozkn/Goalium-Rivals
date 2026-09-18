import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.imports.models import ImportJob
from apps.imports.services import CatalogImporter


class Command(BaseCommand):
    help = "Provider-neutral JSON catalog recordsını PostgreSQL içerik kataloğuna aktarır."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--provider", choices=[choice[0] for choice in ImportJob.PROVIDER_CHOICES], required=True)
        parser.add_argument("--source-url", required=True)
        parser.add_argument("--license-name", required=True)
        parser.add_argument(
            "--license-status",
            choices=[choice[0] for choice in ImportJob._meta.get_field("license_status").choices],
            default="pending",
        )

    def handle(self, *args, **options):
        if options["license_status"] == "blocked":
            raise CommandError("Engellenmiş lisansla içe aktarma yapılamaz.")
        try:
            payload = json.loads(options["file"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"JSON dosyası okunamadı: {exc}") from exc
        records = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(records, list) or not records:
            raise CommandError("JSON, boş olmayan bir records listesi içermelidir.")

        job = ImportJob.objects.create(
            provider=options["provider"],
            source_url=options["source_url"],
            license_name=options["license_name"],
            license_status=options["license_status"],
        )
        result = CatalogImporter().run(job, records)
        self.stdout.write(
            self.style.SUCCESS(
                f"İçe aktarma tamamlandı: {result.imported} içe aktarıldı, "
                f"{result.skipped} atlandı, {result.errors} hata."
            )
        )
