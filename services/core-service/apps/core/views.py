from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema
from django.conf import settings

from .db import get_client
from .models import ProcessedEvent, ActionLog, ManualReviewQueue
from .permissions import HasInternalApiKey
from .serializers import ProcessedEventSerializer, ActionLogSerializer, ManualReviewSerializer


class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(summary="Health check", responses={200: OpenApiResponse(description="OK")})
    def get(self, request):
        checks = {
            "mongo": self._check_mongo(),
            "kafka": {
                "configured": bool(settings.KAFKA_BOOTSTRAP_SERVERS),
                "raw_events_topic": settings.KAFKA_RAW_EVENTS_TOPIC,
                "reply_commands_topic": settings.KAFKA_REPLY_COMMANDS_TOPIC,
                "send_failed_topic": settings.KAFKA_SEND_FAILED_TOPIC,
                "send_retry_topic": settings.KAFKA_SEND_RETRY_TOPIC,
                "dead_letter_topic": settings.KAFKA_DEAD_LETTER_TOPIC,
            },
            "dify": {"configured": bool(settings.DIFY_API_KEY)},
        }
        overall = "ok" if checks["mongo"]["ok"] else "degraded"
        return Response({"status": overall, "service": "core-service", "checks": checks})

    @staticmethod
    def _check_mongo():
        try:
            get_client().admin.command("ping")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


class MetricsAPIView(APIView):
    permission_classes = [HasInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="Core service metrics", responses={200: OpenApiResponse(description="Metrics")})
    def get(self, request):
        try:
            status_counts = ProcessedEvent.count_by_status()
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"processed_events_by_status": status_counts})


class ProcessedEventListAPIView(APIView):
    permission_classes = [HasInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="List processed events", responses={200: ProcessedEventSerializer(many=True)})
    def get(self, request):
        filters = {}

        event_type = request.query_params.get("event_type")
        event_status = request.query_params.get("status")
        page_id = request.query_params.get("page_id")

        if event_type:
            filters["event_type"] = event_type
        if event_status:
            filters["status"] = event_status
        if page_id:
            filters["page_id"] = page_id

        docs = ProcessedEvent.list_events(filters, limit=50)

        # Remove MongoDB _id (not JSON serializable)
        for doc in docs:
            doc.pop("_id", None)

        serializer = ProcessedEventSerializer(docs, many=True)
        return Response(serializer.data)


class ProcessedEventDetailAPIView(APIView):
    permission_classes = [HasInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="Event detail with action logs", responses={200: OpenApiResponse(description="Event detail")})
    def get(self, request, event_id: str):
        doc = ProcessedEvent.find_by_event_id(event_id)
        if not doc:
            return Response({"detail": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

        doc.pop("_id", None)

        # Attach action logs
        actions = ActionLog.find_by_event_id(event_id)
        for a in actions:
            a.pop("_id", None)

        # Attach reviews
        reviews = ManualReviewQueue._col().find({"event_id": event_id})
        review_list = []
        for r in reviews:
            r.pop("_id", None)
            review_list.append(r)

        event_data = ProcessedEventSerializer(doc).data
        event_data["actions"] = ActionLogSerializer(actions, many=True).data
        event_data["reviews"] = ManualReviewSerializer(review_list, many=True).data

        return Response(event_data)


class ProcessedEventRetryAPIView(APIView):
    permission_classes = [HasInternalApiKey]
    authentication_classes = []

    @extend_schema(
        summary="Retry a failed event",
        request=None,
        responses={200: OpenApiResponse(description="Retry result")},
    )
    def post(self, request, event_id: str):
        doc = ProcessedEvent.find_by_event_id(event_id)
        if not doc:
            return Response({"detail": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

        if doc.get("status") not in {"failed", "retrying", "send_failed", "dlq_published"}:
            return Response(
                {"detail": f"Cannot retry event with status={doc.get('status')}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw = doc.get("raw_event", {})

        from .services import EventProcessor
        processor = EventProcessor()
        result = processor.process(raw, force_retry=True)
        result.pop("_id", None)

        return Response(ProcessedEventSerializer(result).data)


class ManualReviewListAPIView(APIView):
    permission_classes = [HasInternalApiKey]
    authentication_classes = []

    @extend_schema(summary="List manual review queue", responses={200: ManualReviewSerializer(many=True)})
    def get(self, request):
        docs = ManualReviewQueue.list_pending(limit=50)
        for doc in docs:
            doc.pop("_id", None)
        serializer = ManualReviewSerializer(docs, many=True)
        return Response(serializer.data)
