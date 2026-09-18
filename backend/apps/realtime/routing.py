from django.urls import re_path

from apps.realtime.consumers import MatchConsumer


websocket_urlpatterns = [
    re_path(r"ws/v1/match/(?P<match_id>[0-9a-f-]+)/$", MatchConsumer.as_asgi()),
]
