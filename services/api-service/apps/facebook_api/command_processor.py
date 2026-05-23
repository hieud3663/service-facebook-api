"""Process asynchronous Facebook action commands from Kafka."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from django.conf import settings

from .services import FacebookGraphService, FacebookServiceError

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


class Publisher(Protocol):
    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        ...


@dataclass
class CommandResult:
    status: str
    command_id: str
    response: dict[str, Any] | None = None
    error: str = ""


class ReplyCommandValidationError(Exception):
    pass


class ReplyCommandProcessor:
    def __init__(
        self,
        publisher: Publisher,
        service: FacebookGraphService | None = None,
        service_class=FacebookGraphService,
    ):
        self.publisher = publisher
        self.service = service
        self.service_class = service_class

    def process(self, command: dict[str, Any]) -> CommandResult:
        normalized = self._validate(command)
        service = self.service or self.service_class()
        command_id = normalized["command_id"]

        try:
            response = self._execute(service, normalized)
        except FacebookServiceError as exc:
            failure_payload = self._build_failure_payload(normalized, exc)
            self.publisher.publish(settings.KAFKA_SEND_FAILED_TOPIC, failure_payload)
            return CommandResult(status="failed_published", command_id=command_id, error=exc.message)

        return CommandResult(status="success", command_id=command_id, response=response)

    @staticmethod
    def _validate(command: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(command, dict):
            raise ReplyCommandValidationError("command must be an object")

        normalized = dict(command)
        if not normalized.get("command_id"):
            raise ReplyCommandValidationError("missing command_id")
        if not normalized.get("event_id"):
            raise ReplyCommandValidationError("missing event_id")

        payload = normalized.get("payload") or {}
        if not isinstance(payload, dict):
            raise ReplyCommandValidationError("payload must be an object")
        normalized["payload"] = payload
        normalized.setdefault("retry_count", 0)
        normalized.setdefault("max_retries", settings.KAFKA_MAX_RETRIES)
        normalized.setdefault("raw_event", {})

        action_type = normalized.get("action_type")
        if action_type == "hide_comment" and not payload.get("comment_id"):
            raise ReplyCommandValidationError("missing comment_id")
        if action_type == "reply_comment" and not (payload.get("comment_id") and payload.get("message")):
            raise ReplyCommandValidationError("missing comment_id or message")
        if action_type == "reply_message" and not (payload.get("recipient_id") and payload.get("message")):
            raise ReplyCommandValidationError("missing recipient_id or message")
        if action_type not in {"hide_comment", "reply_comment", "reply_message"}:
            raise ReplyCommandValidationError(f"unsupported action_type: {action_type}")
        return normalized

    @staticmethod
    def _execute(service: FacebookGraphService, command: dict[str, Any]) -> dict[str, Any]:
        payload = command["payload"]
        action_type = command["action_type"]

        if action_type == "hide_comment":
            return service.hide_comment(payload["comment_id"], is_hidden=payload.get("is_hidden", True))
        if action_type == "reply_comment":
            return service.reply_comment(payload["comment_id"], message=payload["message"])
        if action_type == "reply_message":
            return service.send_message(recipient_id=payload["recipient_id"], message=payload["message"])

        raise ReplyCommandValidationError(f"unsupported action_type: {action_type}")

    @staticmethod
    def _build_failure_payload(command: dict[str, Any], exc: FacebookServiceError) -> dict[str, Any]:
        failure_type, retryable = classify_facebook_failure(exc.message, exc.status_code)
        return {
            "command_id": command["command_id"],
            "event_id": command.get("event_id", ""),
            "action_type": command.get("action_type", ""),
            "target_id": command.get("target_id", ""),
            "page_id": command.get("page_id", ""),
            "retry_count": int(command.get("retry_count", 0) or 0),
            "max_retries": int(command.get("max_retries", settings.KAFKA_MAX_RETRIES) or settings.KAFKA_MAX_RETRIES),
            "retryable": retryable,
            "failure_type": failure_type,
            "reason": exc.message,
            "status_code": exc.status_code,
            "payload": command.get("payload", {}),
            "raw_event": command.get("raw_event", {}),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "source_service": "api-service",
            "facebook_error": exc.details or {},
        }


def classify_facebook_failure(message: str, status_code: int) -> tuple[str, bool]:
    lowered = (message or "").lower()
    if status_code in RETRYABLE_STATUS_CODES:
        if status_code == 429:
            return "rate_limit", True
        if status_code == 408:
            return "api_timeout", True
        return "api_5xx", True
    if status_code in NON_RETRYABLE_STATUS_CODES:
        if status_code in {401, 403}:
            return "permission_denied", False
        if "token" in lowered:
            return "invalid_token", False
        return "validation_error", False
    if "timeout" in lowered:
        return "api_timeout", True
    if "connection" in lowered or "temporar" in lowered:
        return "network_error", True
    return "unknown", True
