from django.urls import reverse
from io import StringIO
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.content.models import Question, SourceReference
from apps.accounts.models import User


class ContentApiTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_superuser(
            email="editor@example.com",
            password="strong-editor-password",
            display_name="Editor",
        )
        self.source = SourceReference.objects.create(
            provider="IFAB",
            url="https://www.theifab.com/laws/latest/offside/",
            license_name="Reference only",
            license_status="verified",
        )
        self.question_payload = {
            "mode": "hangman",
            "difficulty": "easy",
            "payload": {
                "public_payload": {"category": "rule"},
                "answer_data": {"canonical": "ofsayt"},
            },
            "translations": [
                {
                    "language": "tr",
                    "prompt": "Futbolda ofsayt kuralını bulun.",
                    "choices": [],
                    "hints": ["Kural"],
                },
                {
                    "language": "en",
                    "prompt": "Find the offside football rule.",
                    "choices": [],
                    "hints": ["Rule"],
                },
            ],
            "source_ids": [],
        }

    def create_question(self):
        self.question_payload["source_ids"] = [str(self.source.id)]
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(reverse("content-editor-questions"), self.question_payload, format="json")
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def transition(self, question_id, target_status):
        return self.client.post(
            reverse("content-editor-question-transition", kwargs={"question_id": question_id}),
            {"target_status": target_status},
            format="json",
        )

    def test_only_published_questions_are_public_and_answer_data_is_hidden(self):
        question_id = self.create_question()

        self.client.force_authenticate()
        self.assertEqual(self.client.get(reverse("content-public-questions")).data, [])

        self.client.force_authenticate(user=self.editor)
        for target_status in ["in_review", "approved", "published"]:
            response = self.transition(question_id, target_status)
            self.assertEqual(response.status_code, 200, response.data)

        self.client.force_authenticate()
        response = self.client.get(reverse("content-public-question-detail", kwargs={"question_id": question_id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["translation"]["language"], "tr")
        self.assertEqual(response.data["payload"], {"category": "rule"})
        self.assertNotIn("answer_data", response.data)
        self.assertNotIn("canonical", response.data["payload"])

    def test_unverified_source_cannot_be_published(self):
        self.source.license_status = "pending"
        self.source.save(update_fields=["license_status", "updated_at"])
        question_id = self.create_question()

        for target_status in ["in_review", "approved"]:
            response = self.transition(question_id, target_status)
            self.assertEqual(response.status_code, 200, response.data)
        response = self.transition(question_id, "published")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Question.objects.get(id=question_id).status, "approved")

    def test_publish_requires_both_language_translations(self):
        self.question_payload["translations"] = self.question_payload["translations"][:1]
        question_id = self.create_question()

        for target_status in ["in_review", "approved"]:
            response = self.transition(question_id, target_status)
            self.assertEqual(response.status_code, 200, response.data)
        response = self.transition(question_id, "published")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Question.objects.get(id=question_id).status, "approved")

    def test_catalog_validation_command_accepts_published_bilingual_content(self):
        question_id = self.create_question()
        for target_status in ["in_review", "approved", "published"]:
            response = self.transition(question_id, target_status)
            self.assertEqual(response.status_code, 200, response.data)

        output = StringIO()
        call_command("validate_catalog", stdout=output)

        self.assertIn("Catalog validation passed", output.getvalue())
