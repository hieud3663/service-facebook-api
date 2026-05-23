"""Retry decision and payload processing."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from django.conf import settings

from .backoff import calculate_backoff_seconds
from .models import RetryAttempt

RETRYABLE_FAILURE_TYPES = {
    "api_timeout",
    "api_5xx",
    "rate_limit",
    "network_error",
    "temporary_unavailable",
    "circuit_open",
    "unknown",
}

NON_RETRYABLE_FAILURE_TYPES = {
    "validation_error",
    "missing_required_field",
    "invalid_token",
    "permission_denied",
    "unsupported_action",
}


class RetryValidationError(Exception):
    pass


class Publisher(Protocol):
    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        ...


class RetryProcessor:
    def __init__(self, publisher: Publisher, sleep_func=time.sleep):
        self.publisher = publisher
        self.sleep_func = sleep_func

    def process(self, message: dict[str, Any]) -> dict[str, Any]:
        normalized = self._validate(message)
        command_id = normalized["command_id"]
        existing = RetryAttempt.find_by_command_id(command_id)
        retry_count = int(normalized.get("retry_count", 0) or 0)
        max_retries = int(normalized.get("max_retries", settings.RETRY_MAX_ATTEMPTS))

        if existing and existing.get("status") == "dead_lettered":
            return {"status": "skipped", "reason": "already_dead_lettered", "command_id": command_id}

        if not self._is_retryable(normalized) or retry_count >= max_retries:
            payload = self._build_dead_letter_payload(normalized, retry_count, max_retries)
            self.publisher.publish(settings.KAFKA_DEAD_LETTER_TOPIC, payload)
            RetryAttempt.mark_dead_lettered(normalized, retry_count, payload["reason"])
            return {"status": "dead_lettered", "topic": settings.KAFKA_DEAD_LETTER_TOPIC, "payload": payload}

        next_retry_count = retry_count + 1
        scheduled_counts = set((existing or {}).get("scheduled_retry_counts", []))
        if next_retry_count in scheduled_counts:
            return {"status": "skipped", "reason": "duplicate_retry", "command_id": command_id}

        delay = calculate_backoff_seconds(
            retry_count,
            settings.RETRY_BASE_DELAY_SECONDS,
            settings.RETRY_MAX_DELAY_SECONDS,
        )
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        retry_payload = self._build_send_retry_payload(normalized, next_retry_count, next_retry_at)

        if delay > 0:
            self.sleep_func(delay)
        self.publisher.publish(settings.KAFKA_SEND_RETRY_TOPIC, retry_payload)
        RetryAttempt.mark_scheduled(normalized, next_retry_count, next_retry_at)
        return {"status": "scheduled", "topic": settings.KAFKA_SEND_RETRY_TOPIC, "payload": retry_payload}

    def _validate(self, message: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise RetryValidationError("message must be an object")

        normalized = dict(message)
        if not normalized.get("command_id"):
            event_id = normalized.get("event_id", "")
            action_type = normalized.get("action_type", "process_event")
            target_id = normalized.get("target_id") or event_id
            if not event_id:
                raise RetryValidationError("missing command_id")
            normalized["command_id"] = f"{event_id}:{action_type}:{target_id}"

        normalized.setdefault("retry_count", 0)
        normalized.setdefault("max_retries", settings.RETRY_MAX_ATTEMPTS)
        normalized.setdefault("payload", {})
        normalized.setdefault("raw_event", normalized.get("event") or {})
        normalized.setdefault("failure_type", "unknown")
        normalized.setdefault("reason", "send failed")
        return normalized

    @staticmethod
    def _is_retryable(message: dict[str, Any]) -> bool:
        if "retryable" in message:
            return bool(message["retryable"])
        failure_type = message.get("failure_type", "unknown")
        if failure_type in NON_RETRYABLE_FAILURE_TYPES:
            return False
        return failure_type in RETRYABLE_FAILURE_TYPES

    @staticmethod
    def _build_send_retry_payload(message: dict[str, Any], retry_count: int, next_retry_at: datetime) -> dict[str, Any]:
        return {
            "command_id": message["command_id"],
            "event_id": message.get("event_id", ""),
            "action_type": message.get("action_type", ""),
            "target_id": message.get("target_id", ""),
            "page_id": message.get("page_id", ""),
            "retry_count": retry_count,
            "max_retries": int(message.get("max_retries", settings.RETRY_MAX_ATTEMPTS)),
            "scheduled_by": "retry-service",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "next_retry_at": next_retry_at.isoformat(),
            "payload": message.get("payload", {}),
            "raw_event": message.get("raw_event", {}),
            "trace_id": message.get("trace_id", ""),
        }

    @staticmethod
    def _build_dead_letter_payload(message: dict[str, Any], retry_count: int, max_retries: int) -> dict[str, Any]:
        return {
            "dead_letter_id": str(uuid.uuid4()),
            "command_id": message["command_id"],
            "event_id": message.get("event_id", ""),
            "action_type": message.get("action_type", ""),
            "target_id": message.get("target_id", ""),
            "retry_count": retry_count,
            "max_retries": max_retries,
            "failure_type": message.get("failure_type", "unknown"),
            "reason": "max retries exceeded" if retry_count >= max_retries else message.get("reason", ""),
            "first_failed_at": message.get("failed_at", ""),
            "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
            "last_failure": message,
            "original_message": message,
            "processor": "retry-service",
        }

