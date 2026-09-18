from django.urls import path

from apps.quiz import views


urlpatterns = [
    path("modes", views.modes, name="modes"),
    path("practice/sessions", views.practice_sessions, name="practice-sessions"),
    path("practice/sessions/<uuid:session_id>", views.practice_session_detail, name="practice-session-detail"),
    path("practice/sessions/<uuid:session_id>/answers", views.practice_answers, name="practice-answers"),
    path("duels", views.duels, name="duels"),
    path("duels/<uuid:duel_id>", views.duel_detail, name="duel-detail"),
    path("duels/<uuid:duel_id>/join", views.duel_join, name="duel-join"),
    path("duels/<uuid:duel_id>/play", views.duel_play, name="duel-play"),
    path("rooms", views.rooms, name="rooms"),
    path("rooms/<str:room_code>", views.room_detail, name="room-detail"),
    path("rooms/<str:room_code>/join", views.room_join, name="room-join"),
    path("rooms/<str:room_code>/start", views.room_start, name="room-start"),
    path("rooms/<str:room_code>/answers", views.room_answers, name="room-answers"),
    path("matches", views.matches, name="matches"),
    path("matches/<uuid:match_id>", views.match_detail, name="match-detail"),
    path("matches/<uuid:match_id>/join", views.match_join, name="match-join"),
]
