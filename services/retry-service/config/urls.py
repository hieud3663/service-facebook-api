from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("retry/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("retry/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("retry/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("retry/", include("apps.retry.urls")),
]

