"""Kafka publisher for asynchronous Facebook action commands."""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class ReplyCommandPublishError(Exception):
    """Raised when core cannot publish an action command to Kafka."""


class ReplyCommandPublisher:
    """Publish outbound Facebook action commands for api-service workers."""

    def __init__(self, topic: str | None = None):
        self.topic = topic or settings.KAFKA_REPLY_COMMANDS_TOPIC
        self._producer = None

    def publish(self, command: dict[str, Any]) -> dict[str, Any]:
        producer = self._get_producer()
        try:
            future = producer.send(self.topic, command)
            future.get(timeout=settings.KAFKA_PRODUCER_SEND_TIMEOUT_SECONDS)
            producer.flush()
        except Exception as exc:
            raise ReplyCommandPublishError(f"reply_commands publish failed: {exc}") from exc

        logger.info(
            "Published reply command %s action=%s topic=%s",
            command.get("command_id", ""),
            command.get("action_type", ""),
            self.topic,
        )
        return {"topic": self.topic, "queued_at": command.get("queued_at")}

    def close(self) -> None:
        if self._producer is not None:
            self._producer.close()
            self._producer = None

    def _get_producer(self):
        if self._producer is None:
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=True, default=str).encode("utf-8"),
                api_version_auto_timeout_ms=settings.KAFKA_API_VERSION_AUTO_TIMEOUT_MS,
            )
        return self._producer


def build_reply_command(
    event: dict[str, Any],
    decision,
    command_id: str,
    retry_count: int = 0,
    max_retries: int | None = None,
) -> dict[str, Any]:
    """Build the Kafka contract consumed by api-service."""
    payload = dict(decision.payload or {})
    target_id = payload.get("comment_id") or payload.get("recipient_id") or payload.get("target_id") or event.get("target_id", "")
    now = datetime.now(timezone.utc).isoformat()
    return {
        "command_id": command_id,
        "event_id": event.get("event_id", ""),
        "action_type": decision.action_type,
        "target_id": target_id,
        "page_id": event.get("page_id", payload.get("page_id", "")),
        "payload": payload,
        "raw_event": event,
        "retry_count": retry_count,
        "max_retries": max_retries if max_retries is not None else settings.KAFKA_MAX_RETRIES,
        "source_service": "core-service",
        "queued_at": now,
        "trace_id": event.get("trace_id", event.get("event_id", "")),
    }
