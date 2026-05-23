from django.urls import path

from .views import (
    RetryAttemptDetailAPIView,
    RetryAttemptListAPIView,
    RetryHealthAPIView,
    RetryMetricsAPIView,
)

urlpatterns = [
    path("health", RetryHealthAPIView.as_view(), name="retry-health"),
    path("attempts", RetryAttemptListAPIView.as_view(), name="retry-attempts"),
    path("attempts/<str:command_id>", RetryAttemptDetailAPIView.as_view(), name="retry-attempt-detail"),
    path("metrics", RetryMetricsAPIView.as_view(), name="retry-metrics"),
]

