import logging

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

logger = logging.getLogger(__name__)


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

        logger.info("Facebook webhook verification requested mode=%s", mode)
        if mode != "subscribe":
            logger.warning("Facebook webhook verification rejected: invalid mode=%s", mode)
            return Response({"detail": "Invalid hub.mode"}, status=status.HTTP_400_BAD_REQUEST)

        if not self.verifier_class.is_valid_verify_token(verify_token):
            logger.warning("Facebook webhook verification rejected: invalid verify token")
            return Response({"detail": "Invalid verify token"}, status=status.HTTP_403_FORBIDDEN)

        logger.info("Facebook webhook verification accepted")
        return HttpResponse(challenge, content_type="text/plain", status=status.HTTP_200_OK)

    def post(self, request):
        signature = request.headers.get("X-Hub-Signature-256")
        logger.info("Facebook webhook payload received")

        try:
            self.verifier_class.verify_signature(request.body, signature)
        except WebhookSignatureError as exc:
            logger.warning("Facebook webhook signature rejected: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        logger.info("Facebook webhook signature accepted object=%s", request.data.get("object", "unknown"))
        events = self.normalizer_class.normalize(request.data)
        logger.info("Facebook webhook payload normalized events=%d", len(events))

        publisher = self.publisher_class()
        try:
            published_count = publisher.publish(events)
        except KafkaPublishError as exc:
            logger.exception("Facebook webhook publish failed")
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        logger.info(
            "Facebook webhook accepted normalized=%d published=%d topic=%s",
            len(events),
            published_count,
            publisher.topic,
        )
        return Response(
            {
                "status": "accepted",
                "normalized_count": len(events),
                "published_count": published_count,
                "topic": publisher.topic,
            },
            status=status.HTTP_202_ACCEPTED,
        )


from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers


class FacebookCommentSubscriptionAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    service_class = FacebookSubscriptionService

    @extend_schema(
        request=inline_serializer(
            name="SubscriptionRequest",
            fields={
                "page_id": serializers.CharField(required=True, help_text="ID của Fanpage cần đăng ký nhận Notification")
            },
        ),
        responses={200: inline_serializer("SubscriptionResponse", {"status": serializers.CharField(), "page_id": serializers.CharField()})}
    )
    def post(self, request):
        page_id = request.data.get("page_id")
        if not page_id:
            logger.warning("Facebook subscription rejected: missing page_id")
            return Response({"detail": "Missing page_id"}, status=status.HTTP_400_BAD_REQUEST)

        service = self.service_class()
        try:
            logger.info("Subscribing page_id=%s to Facebook comment events", page_id)
            result = service.subscribe_page_comment_events(page_id=page_id)
        except FacebookSubscriptionError as exc:
            logger.exception("Facebook subscription failed page_id=%s", page_id)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        logger.info("Facebook subscription completed page_id=%s", page_id)
        return Response(
            {
                "status": "subscribed",
                "page_id": page_id,
                "subscribed_fields": ["feed"],
                "facebook_response": result,
            },
            status=status.HTTP_200_OK,
        )
