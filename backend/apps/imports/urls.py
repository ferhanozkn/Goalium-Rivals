from django.urls import path

from apps.imports import views


urlpatterns = [
    path("content/imports", views.imports_create, name="content-imports-create"),
    path("content/imports/<uuid:job_id>", views.imports_detail, name="content-imports-detail"),
]
