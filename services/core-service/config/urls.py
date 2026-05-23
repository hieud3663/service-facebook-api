from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("core/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("core/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("core/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("core/", include("apps.core.urls")),
]
