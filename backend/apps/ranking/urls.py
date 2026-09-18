from django.urls import path

from apps.ranking import views


urlpatterns = [
    path("matchmaking/queue", views.queue, name="matchmaking-queue"),
    path("matchmaking/queue/status", views.queue_status, name="matchmaking-queue-status"),
    path("leaderboard", views.leaderboard_view, name="leaderboard"),
    path("me/stats", views.me_stats, name="me-stats"),
]
