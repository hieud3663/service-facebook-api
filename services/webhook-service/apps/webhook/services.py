import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookSignatureError(Exception):
    pass


class KafkaPublishError(Exception):
    pass


class FacebookSubscriptionError(Exception):
    pass


class FacebookWebhookVerifier:
    """Validate Facebook webhook handshake and signatures."""

    @staticmethod
    def is_valid_verify_token(token: str) -> bool:
        return token == settings.FACEBOOK_WEBHOOK_VERIFY_TOKEN

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: str | None) -> None:
        if not signature_header:
            raise WebhookSignatureError("Missing X-Hub-Signature-256 header")

        if not signature_header.startswith("sha256="):
            raise WebhookSignatureError("Invalid signature format")

        received_signature = signature_header.split("=", 1)[1]
        secret = settings.FACEBOOK_WEBHOOK_SECRET.encode("utf-8")
        expected_signature = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(received_signature, expected_signature):
            raise WebhookSignatureError("Invalid webhook signature")


class FacebookEventNormalizer:
    """Normalize Facebook payloads into a single schema."""

    @staticmethod
    def _to_iso8601(value: Any) -> str:
        if isinstance(value, str):
            return value

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()

        return datetime.now(tz=timezone.utc).isoformat()

    @classmethod
    def _normalize_change(cls, payload_object: str, entry: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
        value = change.get("value", {})
        from_obj = value.get("from", {})
        field = change.get("field", "")
        item = value.get("item", "")

        if field == "feed" and item == "comment":
            event_type = "comment"
        else:
            event_type = "unknown"

        return {
            "event_id": str(uuid.uuid4()),
            "source": "facebook",
            "object": payload_object,
            "event_type": event_type,
            "occurred_at": cls._to_iso8601(value.get("created_time")),
            "page_id": entry.get("id"),
            "sender_id": from_obj.get("id"),
            "target_id": value.get("post_id") or value.get("comment_id"),
            "channel": "facebook_page",
            "meta": {
                "field": field,
                "item": item,
                "verb": value.get("verb"),
                "comment_id": value.get("comment_id"),
                "parent_id": value.get("parent_id"),
            },
            "raw_event": change,
        }

    @classmethod
    def _normalize_message(
        cls,
        payload_object: str,
        entry: dict[str, Any],
        message_event: dict[str, Any],
    ) -> dict[str, Any]:
        message_payload = message_event.get("message", {})

        return {
            "event_id": str(uuid.uuid4()),
            "source": "facebook",
            "object": payload_object,
            "event_type": "message",
            "occurred_at": cls._to_iso8601(message_event.get("timestamp")),
            "page_id": entry.get("id"),
            "sender_id": message_event.get("sender", {}).get("id"),
            "target_id": message_event.get("recipient", {}).get("id"),
            "channel": "facebook_messenger",
            "meta": {
                "mid": message_payload.get("mid"),
                "is_echo": message_payload.get("is_echo", False),
            },
            "raw_event": message_event,
        }

    @classmethod
    def normalize(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        payload_object = payload.get("object", "unknown")
        entries = payload.get("entry", [])
        normalized_events: list[dict[str, Any]] = []

        for entry in entries:
            for change in entry.get("changes", []):
                normalized_events.append(cls._normalize_change(payload_object, entry, change))

            for message_event in entry.get("messaging", []):
                normalized_events.append(cls._normalize_message(payload_object, entry, message_event))

        return normalized_events


class KafkaRawEventPublisher:
    """Publish normalized events to Kafka topic raw_events."""

    def __init__(self) -> None:
        self.topic = settings.KAFKA_RAW_EVENTS_TOPIC
        self._producer = None

    def _get_producer(self):
        if self._producer is not None:
            return self._producer

        try:
            from kafka import KafkaProducer
        except ImportError as exc:  # pragma: no cover
            raise KafkaPublishError("kafka-python is not installed") from exc

        self._producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id=settings.KAFKA_CLIENT_ID,
            acks=settings.KAFKA_ACKS,
            value_serializer=lambda value: json.dumps(value, ensure_ascii=True).encode("utf-8"),
        )
        return self._producer

    def publish(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0

        producer = self._get_producer()
        published_count = 0

        try:
            for event in events:
                future = producer.send(self.topic, event)
                future.get(timeout=settings.KAFKA_PUBLISH_TIMEOUT_SECONDS)
                published_count += 1
            producer.flush()
            return published_count
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to publish events to Kafka topic %s", self.topic)
            raise KafkaPublishError("Failed to publish events to Kafka") from exc


class FacebookSubscriptionService:
    """Register page webhook subscriptions on Facebook Graph API."""

    def __init__(self) -> None:
        self.version = settings.FACEBOOK_GRAPH_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.version}"
        self.access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN

    def subscribe_page_comment_events(self, page_id: str) -> dict[str, Any]:
        if not self.access_token:
            raise FacebookSubscriptionError("Missing FACEBOOK_PAGE_ACCESS_TOKEN in environment")

        params = {
            "access_token": self.access_token,
        }
        data = {
            "subscribed_fields": "feed",
        }

        query = urlencode(params)
        encoded_body = urlencode(data).encode("utf-8")
        url = f"{self.base_url}/{page_id}/subscribed_apps?{query}"
        request = Request(url=url, data=encoded_body, method="POST")

        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload) if payload else {"success": True}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                details = json.loads(raw)
            except json.JSONDecodeError:
                details = {"raw": raw}
            message = details.get("error", {}).get("message", "Facebook subscription error")
            raise FacebookSubscriptionError(message) from exc
        except URLError as exc:
            raise FacebookSubscriptionError(f"Connection error: {exc.reason}") from exc
