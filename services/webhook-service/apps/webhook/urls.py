from django.urls import path

from .views import FacebookCommentSubscriptionAPIView, FacebookWebhookAPIView

urlpatterns = [
    path("webhook", FacebookWebhookAPIView.as_view(), name="facebook-webhook"),
    path(
        "webhook/subscriptions/comments",
        FacebookCommentSubscriptionAPIView.as_view(),
        name="facebook-comment-subscription",
    ),
]
