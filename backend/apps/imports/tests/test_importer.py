from django.urls import reverse
from rest_framework.test import APITestCase

from apps.content.models import Competition, Player, Season, Team
from apps.accounts.models import User


class ImportApiTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_superuser(
            email="importer@example.com",
            password="strong-importer-password",
            display_name="Importer",
        )
        self.records = [
            {
                "record_type": "competition",
                "external_id": "openfootball:world-cup",
                "name": "FIFA World Cup",
                "country_code": "INT",
                "kind": "international",
            },
            {
                "record_type": "season",
                "external_id": "openfootball:world-cup:2018",
                "competition_external_id": "openfootball:world-cup",
                "label": "2018",
                "start_year": 2018,
                "end_year": 2018,
            },
            {
                "record_type": "team",
                "external_id": "openfootball:france",
                "name": "France",
                "country_code": "FRA",
            },
            {
                "record_type": "player",
                "external_id": "wikidata:Q123",
                "name": "Antoine Griezmann",
                "nationality": "FRA",
            },
        ]

    def test_staff_can_import_provider_neutral_records_idempotently(self):
        self.client.force_authenticate(user=self.editor)
        payload = {
            "provider": "openfootball",
            "source_url": "https://github.com/openfootball/football.json",
            "license_name": "CC0",
            "license_status": "verified",
            "records": self.records,
        }

        first = self.client.post(reverse("content-imports-create"), payload, format="json")
        second = self.client.post(reverse("content-imports-create"), payload, format="json")

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["status"], "completed")
        self.assertEqual(first.data["imported_count"], 4)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(Competition.objects.filter(external_id="openfootball:world-cup").count(), 1)
        self.assertEqual(Season.objects.filter(external_id="openfootball:world-cup:2018").count(), 1)
        self.assertEqual(Team.objects.filter(external_id="openfootball:france").count(), 1)
        self.assertEqual(Player.objects.filter(external_id="wikidata:Q123").count(), 1)
