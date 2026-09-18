from django.urls import path

from apps.accounts import views


urlpatterns = [
    path("auth/register", views.register, name="auth-register"),
    path("auth/login", views.login, name="auth-login"),
    path("guest/session", views.guest_session, name="guest-session"),
    path("me", views.me, name="me"),
]
