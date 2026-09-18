from django.urls import path

from apps.content import views


urlpatterns = [
    path("content/questions", views.public_questions, name="content-public-questions"),
    path("content/questions/<uuid:question_id>", views.public_question_detail, name="content-public-question-detail"),
    path("content/editor/sources", views.editor_sources, name="content-editor-sources"),
    path("content/editor/questions", views.editor_questions, name="content-editor-questions"),
    path("content/editor/questions/<uuid:question_id>", views.editor_question_detail, name="content-editor-question-detail"),
    path(
        "content/editor/questions/<uuid:question_id>/transition",
        views.editor_question_transition,
        name="content-editor-question-transition",
    ),
]
