from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .db import get_client
from .models import RetryAttempt
from .permissions import HasRetryInternalApiKey
from .serializers import RetryAttemptSerializer


class RetryHealthAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(summary="Retry service health", responses={200: OpenApiResponse(description="OK")})
    def get(self, request):
        mongo = self._check_mongo()
        status_text = "ok" if mongo["ok"] else "degraded"
        return Response(
            {
                "status": status_text,
                "service": "retry-service",
                "checks": {
                    "mongo": mongo,
                    "kafka": {
                        "configured": bool(settings.KAFKA_BOOTSTRAP_SERVERS),
                        "send_failed_topic": settings.KAFKA_SEND_FAILED_TOPIC,
                        "send_retry_topic": settings.KAFKA_SEND_RETRY_TOPIC,
                        "dead_letter_topic": settings.KAFKA_DEAD_LETTER_TOPIC,
                    },
                },
            }
        )

    @staticmethod
    def _check_mongo():
        try:
            get_client().admin.command("ping")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


class RetryAttemptListAPIView(APIView):
    permission_classes = [HasRetryInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="List retry attempts", responses={200: RetryAttemptSerializer(many=True)})
    def get(self, request):
        filters = {}
        status_filter = request.query_params.get("status")
        if status_filter:
            filters["status"] = status_filter
        docs = RetryAttempt.list_attempts(filters, limit=50)
        for doc in docs:
            doc.pop("_id", None)
        return Response(RetryAttemptSerializer(docs, many=True).data)


class RetryAttemptDetailAPIView(APIView):
    permission_classes = [HasRetryInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="Retry attempt detail", responses={200: RetryAttemptSerializer})
    def get(self, request, command_id: str):
        doc = RetryAttempt.find_by_command_id(command_id)
        if not doc:
            return Response({"detail": "Retry attempt not found"}, status=status.HTTP_404_NOT_FOUND)
        doc.pop("_id", None)
        return Response(RetryAttemptSerializer(doc).data)


class RetryMetricsAPIView(APIView):
    permission_classes = [HasRetryInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="Retry metrics", responses={200: OpenApiResponse(description="Metrics")})
    def get(self, request):
        try:
            counts = RetryAttempt.count_by_status()
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"retry_attempts_by_status": counts})

