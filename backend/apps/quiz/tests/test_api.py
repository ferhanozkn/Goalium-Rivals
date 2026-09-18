from django.urls import reverse
from rest_framework.test import APITestCase


class QuizApiTests(APITestCase):
    def test_modes_are_public_and_return_fixed_contract(self):
        response = self.client.get(reverse("modes"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 5)
        self.assertEqual(response.data[0]["id"], "hangman")
        self.assertNotIn("answer", response.data[0])

    def test_guest_can_create_and_join_live_match(self):
        first = self.client.post(reverse("guest-session"), {"display_name": "First"}, format="json")
        self.client.credentials(HTTP_X_GUEST_TOKEN=first.data["guest_token"])
        created = self.client.post(reverse("matches"), {"language": "tr", "is_mixed": True, "origin": "invite"}, format="json")

        self.assertEqual(created.status_code, 201)
        match_id = created.data["id"]

        second = self.client.post(reverse("guest-session"), {"display_name": "Second"}, format="json")
        self.client.credentials(HTTP_X_GUEST_TOKEN=second.data["guest_token"])
        joined = self.client.post(reverse("match-join", kwargs={"match_id": match_id}), {}, format="json")

        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.data["match"]["status"], "live")
        self.assertEqual(len(joined.data["match"]["participants"]), 2)
