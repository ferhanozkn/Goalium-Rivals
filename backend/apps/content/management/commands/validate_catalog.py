from django.core.management.base import BaseCommand, CommandError

from apps.content.constants import LANGUAGE_CHOICES
from apps.content.models import Question


class Command(BaseCommand):
    help = "Yayınlanmış soruların iki dil, payload ve doğrulanmış kaynak koşullarını denetler."

    def handle(self, *args, **options):
        required_languages = {language for language, _ in LANGUAGE_CHOICES}
        failures: list[str] = []
        published = Question.objects.filter(status="published").prefetch_related("translations", "source_references")
        for question in published:
            languages = set(question.translations.values_list("language", flat=True))
            missing_languages = required_languages - languages
            if missing_languages:
                failures.append(f"{question.id}: missing translations {sorted(missing_languages)}")
            if not hasattr(question, "payload"):
                failures.append(f"{question.id}: missing payload")
            if not question.source_references.exists():
                failures.append(f"{question.id}: missing source")
            elif question.source_references.exclude(license_status="verified").exists():
                failures.append(f"{question.id}: unverified source")

        if failures:
            for failure in failures:
                self.stderr.write(self.style.ERROR(failure))
            raise CommandError(f"Catalog validation failed: {len(failures)} issue(s).")

        self.stdout.write(self.style.SUCCESS(f"Catalog validation passed: {published.count()} published question(s)."))
