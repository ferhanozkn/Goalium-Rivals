from django.test import SimpleTestCase

from apps.realtime.routing import websocket_urlpatterns


class RealtimeRoutingTests(SimpleTestCase):
    def test_match_route_is_registered(self):
        self.assertEqual(len(websocket_urlpatterns), 1)
