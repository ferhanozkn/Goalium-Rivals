from django.urls import reverse
from rest_framework.test import APITestCase


class AccountApiTests(APITestCase):
    def test_guest_session_can_be_created_and_used_for_me(self):
        response = self.client.post(reverse("guest-session"), {"display_name": "Test Guest"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.client.credentials(HTTP_X_GUEST_TOKEN=response.data["guest_token"])

        me_response = self.client.get(reverse("me"))

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["type"], "guest")
        self.assertEqual(me_response.data["display_name"], "Test Guest")

    def test_register_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "email": "player@example.com",
                "password": "a-strong-test-password",
                "display_name": "Player",
                "preferred_language": "tr",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
