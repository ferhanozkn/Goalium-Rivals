from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.health import health


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.content.urls")),
    path("api/v1/", include("apps.imports.urls")),
    path("api/v1/", include("apps.quiz.urls")),
    path("api/v1/", include("apps.ranking.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/health", health, name="health"),
]
