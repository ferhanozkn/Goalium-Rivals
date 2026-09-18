from django.urls import path

from apps.quiz import views


urlpatterns = [
    path("modes", views.modes, name="modes"),
    path("practice/sessions", views.practice_sessions, name="practice-sessions"),
    path("practice/sessions/<uuid:session_id>", views.practice_session_detail, name="practice-session-detail"),
    path("practice/sessions/<uuid:session_id>/answers", views.practice_answers, name="practice-answers"),
    path("matches", views.matches, name="matches"),
    path("matches/<uuid:match_id>", views.match_detail, name="match-detail"),
    path("matches/<uuid:match_id>/join", views.match_join, name="match-join"),
]
