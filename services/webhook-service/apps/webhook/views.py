from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    FacebookEventNormalizer,
    FacebookSubscriptionError,
    FacebookSubscriptionService,
    FacebookWebhookVerifier,
    KafkaPublishError,
    KafkaRawEventPublisher,
    WebhookSignatureError,
)


class FacebookWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    verifier_class = FacebookWebhookVerifier
    normalizer_class = FacebookEventNormalizer
    publisher_class = KafkaRawEventPublisher

    def get(self, request):
        mode = request.query_params.get("hub.mode")
        verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")

        if mode != "subscribe":
            return Response({"detail": "Invalid hub.mode"}, status=status.HTTP_400_BAD_REQUEST)

        if not self.verifier_class.is_valid_verify_token(verify_token):
            return Response({"detail": "Invalid verify token"}, status=status.HTTP_403_FORBIDDEN)

        return HttpResponse(challenge, content_type="text/plain", status=status.HTTP_200_OK)

    def post(self, request):
        signature = request.headers.get("X-Hub-Signature-256")

        try:
            self.verifier_class.verify_signature(request.body, signature)
        except WebhookSignatureError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        events = self.normalizer_class.normalize(request.data)

        publisher = self.publisher_class()
        try:
            published_count = publisher.publish(events)
        except KafkaPublishError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "status": "accepted",
                "normalized_count": len(events),
                "published_count": published_count,
                "topic": publisher.topic,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class FacebookCommentSubscriptionAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    service_class = FacebookSubscriptionService

    def post(self, request):
        page_id = request.data.get("page_id")
        if not page_id:
            return Response({"detail": "Missing page_id"}, status=status.HTTP_400_BAD_REQUEST)

        service = self.service_class()
        try:
            result = service.subscribe_page_comment_events(page_id=page_id)
        except FacebookSubscriptionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "status": "subscribed",
                "page_id": page_id,
                "subscribed_fields": ["feed"],
                "facebook_response": result,
            },
            status=status.HTTP_200_OK,
        )
