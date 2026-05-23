from django.urls import path

from .views import (
    HealthCheckAPIView,
    ManualReviewListAPIView,
    MetricsAPIView,
    ProcessedEventDetailAPIView,
    ProcessedEventListAPIView,
    ProcessedEventRetryAPIView,
)

urlpatterns = [
    path("health", HealthCheckAPIView.as_view(), name="core-health"),
    path("metrics", MetricsAPIView.as_view(), name="core-metrics"),
    path("events", ProcessedEventListAPIView.as_view(), name="core-events"),
    path("events/<str:event_id>", ProcessedEventDetailAPIView.as_view(), name="core-event-detail"),
    path("events/<str:event_id>/retry", ProcessedEventRetryAPIView.as_view(), name="core-event-retry"),
    path("reviews", ManualReviewListAPIView.as_view(), name="core-reviews"),
]
