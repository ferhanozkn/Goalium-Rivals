from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.content.models import Question


class Command(BaseCommand):
    help = "Lisansı doğrulanmış pilot soru draftlarını yayınlar; hak incelemesi bekleyenleri atlar."

    def add_arguments(self, parser):
        parser.add_argument("--prefix", default="pilot:", help="Yayınlanacak seed_key öneki.")
        parser.add_argument("--confirm", action="store_true", help="Yayın işlemini onaylar.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Yayınlamak için --confirm parametresi zorunludur.")

        questions = Question.objects.filter(status="draft", seed_key__startswith=options["prefix"])
        published = 0
        skipped_license = 0
        skipped_invalid = 0

        for question in questions:
            if question.source_references.exclude(license_status="verified").exists():
                skipped_license += 1
                continue
            try:
                question.validate_publishable()
            except ValidationError as exc:
                skipped_invalid += 1
                self.stdout.write(self.style.WARNING(f"Atlandı {question.seed_key}: {exc}"))
                continue

            now = timezone.now()
            question.status = "published"
            question.approved_at = question.approved_at or now
            question.published_at = question.published_at or now
            question.save(update_fields=["status", "approved_at", "published_at", "updated_at"])
            published += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Soru yayınlama tamamlandı: {published} yayınlandı, "
                f"{skipped_license} lisans nedeniyle atlandı, {skipped_invalid} doğrulama nedeniyle atlandı."
            )
        )
