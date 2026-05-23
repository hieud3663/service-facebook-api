"""Failure payload helpers shared by core Kafka workers."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


RETRYABLE_FAILURE_TYPES = {
    "api_timeout",
    "api_5xx",
    "network_error",
    "rate_limit",
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


def build_command_id(event: dict[str, Any], action_type: str = "", target_id: str = "") -> str:
    event_id = event.get("event_id", "")
    if not action_type:
        action_type = event.get("decision") or event.get("action_type") or "process_event"
    if not target_id:
        target_id = (
            event.get("comment_id")
            or event.get("target_id")
            or event.get("sender_id")
            or event_id
        )
    return f"{event_id}:{action_type}:{target_id}"


def classify_failure(message: str = "", status_code: int | None = None) -> tuple[str, bool]:
    text = (message or "").lower()
    if "timeout" in text:
        return "api_timeout", True
    if "circuit" in text and "open" in text:
        return "circuit_open", True
    if "unreachable" in text or "connection" in text:
        return "network_error", True
    if status_code == 429:
        return "rate_limit", True
    if status_code in {401, 403}:
        return "permission_denied", False
    if status_code and 400 <= status_code < 500:
        return "validation_error", False
    if status_code and status_code >= 500:
        return "api_5xx", True
    return "unknown", True


def build_failure_payload(
    event: dict[str, Any],
    result: dict[str, Any] | None = None,
    retry_count: int = 0,
    max_retries: int = 3,
    source_service: str = "core-service",
) -> dict[str, Any]:
    result = result or {}
    reason = result.get("error_message") or result.get("reason") or "processing failed"
    status_code = result.get("status_code")
    failure_type = result.get("failure_type")
    retryable = result.get("retryable")
    if not failure_type:
        failure_type, inferred_retryable = classify_failure(reason, status_code)
        if retryable is None:
            retryable = inferred_retryable
    if retryable is None:
        retryable = failure_type in RETRYABLE_FAILURE_TYPES

    action_type = result.get("decision") or result.get("action_type") or event.get("decision") or "process_event"
    target_id = (
        result.get("target_id")
        or event.get("comment_id")
        or event.get("target_id")
        or event.get("sender_id")
        or ""
    )

    return {
        "failure_id": str(uuid.uuid4()),
        "command_id": build_command_id(event, action_type=action_type, target_id=target_id),
        "event_id": event.get("event_id", ""),
        "action_type": action_type,
        "target_id": target_id,
        "page_id": event.get("page_id", ""),
        "retry_count": retry_count,
        "max_retries": max_retries,
        "retryable": bool(retryable),
        "failure_type": failure_type,
        "reason": reason,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "next_retry_at": None,
        "payload": result.get("request_payload") or result.get("payload") or {},
        "raw_event": event,
        "last_action": result.get("last_action") or {},
        "source_service": source_service,
        "trace_id": result.get("trace_id", ""),
    }

