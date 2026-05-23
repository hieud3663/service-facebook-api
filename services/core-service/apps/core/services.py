"""Core event processing pipeline."""
import logging
from datetime import datetime, timezone
from typing import Any

from .decisions import ActionDecision, DecisionEngine
from .failures import build_command_id
from .models import ActionLog, ManualReviewQueue, ProcessedEvent
from .reply_commands import ReplyCommandPublishError, ReplyCommandPublisher, build_reply_command

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"processed", "ignored", "action_queued", "review_pending", "dlq_published"}
RETRYABLE_STATUSES = {"failed", "retrying", "send_failed"}


class EventProcessor:
    """
    Orchestrates the full processing pipeline for a single event:
      1. Deduplicate/idempotency guard
      2. Persist as ProcessedEvent (status=received/retrying)
      3. Run DecisionEngine
      4. Queue action command for api-service
      5. Log result and final status
    """

    def __init__(self, reply_publisher: ReplyCommandPublisher | None = None):
        self.decision_engine = DecisionEngine()
        self.reply_publisher = reply_publisher or ReplyCommandPublisher()

    def process(self, event: dict[str, Any], force_retry: bool = False) -> dict:
        event_id = event.get("event_id", "")
        if not event_id:
            return {"status": "failed", "error_message": "missing event_id", "raw_event": event}

        # ── 1. Deduplicate / idempotency ──
        existing = ProcessedEvent.find_by_event_id(event_id)
        if existing:
            current_status = existing.get("status", "")
            if current_status in TERMINAL_STATUSES and not force_retry:
                logger.info("Duplicate terminal event %s status=%s, skipping", event_id[:8], current_status)
                return existing
            if current_status not in RETRYABLE_STATUSES and not force_retry:
                logger.info("Duplicate in-flight event %s status=%s, skipping", event_id[:8], current_status)
                return existing

            retry_count = int(existing.get("retry_count", 0) or 0) + (1 if force_retry else 0)
            ProcessedEvent.update_by_event_id(
                event_id,
                status="retrying",
                retry_count=retry_count,
                error_message="",
            )
            record = ProcessedEvent.find_by_event_id(event_id) or existing
        else:
            # ── 2. Persist ──
            occurred_at = self._parse_datetime(event.get("occurred_at"))
            record = ProcessedEvent.create(
                event_id=event_id,
                platform_event_id=event.get("platform_event_id", ""),
                source=event.get("source", "facebook"),
                event_type=event.get("event_type", "unknown"),
                channel=event.get("channel", ""),
                page_id=event.get("page_id", ""),
                sender_id=event.get("sender_id", ""),
                actor_name=event.get("actor_name", ""),
                target_id=event.get("target_id", ""),
                post_id=event.get("post_id", ""),
                comment_id=event.get("comment_id", ""),
                parent_id=event.get("parent_id", ""),
                message_text=event.get("message_text", ""),
                status="received",
                raw_event=event,
                occurred_at=occurred_at,
            )

        # ── 3. Decide ──
        try:
            decision = self.decision_engine.decide(event)
        except Exception as exc:
            logger.exception("Decision engine failed for event %s", event_id[:8])
            failed_fields = {
                "status": "failed",
                "error_message": str(exc),
                "last_failed_at": datetime.now(timezone.utc),
            }
            ProcessedEvent.update_by_event_id(event_id, **failed_fields)
            record.update(failed_fields)
            return record

        update_fields = self._build_analysis_update(decision)

        # ── 4. Execute ──
        action_status = "skipped"
        action_error = ""
        if decision.should_execute:
            action_status, action_error = self._execute_action(event, record, decision)
            if action_status == "failed":
                final_status = "failed"
            elif decision.action_type in {"hide_comment", "reply_comment", "reply_message"}:
                final_status = "action_queued" if action_status == "queued" else "processed"
            elif decision.action_type == "escalate":
                final_status = "review_pending"
            else:
                final_status = "processed"
        else:
            final_status = "ignored" if decision.action_type == "ignore" else "processed"

        # ── 5. Handle escalation (manual review queue) ──
        if action_status != "failed" and (decision.action_type == "escalate" or decision.payload.get("escalate")):
            ManualReviewQueue.create(event_id=event_id, reason=decision.reason)
            final_status = "review_pending"

        update_fields["status"] = final_status
        update_fields["error_message"] = action_error
        if final_status == "failed":
            update_fields["last_failed_at"] = datetime.now(timezone.utc)

        ProcessedEvent.update_by_event_id(event_id, **update_fields)
        record.update(update_fields)

        logger.info(
            "Event %s → decision=%s reason=%s status=%s",
            event_id[:8], decision.action_type, decision.reason, final_status,
        )
        return record

    def _build_analysis_update(self, decision: ActionDecision) -> dict[str, Any]:
        update_fields: dict[str, Any] = {
            "decision": decision.action_type,
            "decision_reason": decision.reason,
        }
        if decision.ai_result:
            update_fields.update(
                {
                    "intent": decision.ai_result.intent,
                    "sentiment": decision.ai_result.sentiment,
                    "is_spam": decision.ai_result.is_spam,
                    "is_malicious_link": decision.ai_result.is_malicious_link,
                    "ai_confidence": decision.ai_result.confidence,
                    "ai_reason": decision.ai_result.reason,
                    "ai_parse_error": decision.ai_result.parse_error,
                    "ai_raw_response": decision.ai_result.raw_response,
                }
            )
        if decision.spam_result:
            update_fields.update(
                {
                    "message_hash": decision.spam_result.message_hash,
                    "is_spam": bool(update_fields.get("is_spam", False) or decision.spam_result.is_spam),
                    "is_malicious_link": bool(
                        update_fields.get("is_malicious_link", False) or decision.spam_result.is_malicious_link
                    ),
                    "spam_score": decision.spam_result.score,
                    "spam_signals": decision.spam_result.signals,
                    "spam_reason": decision.spam_result.reason,
                    "detected_links": decision.spam_result.links,
                }
            )
        return update_fields

    def _execute_action(self, event: dict[str, Any], record: dict[str, Any], decision: ActionDecision) -> tuple[str, str]:
        """Publish the decided action as a Kafka command for api-service."""
        event_id = event.get("event_id", "")
        idempotency_key = self._build_action_idempotency_key(event_id, decision)
        success_log = ActionLog.find_success_by_idempotency_key(idempotency_key)
        if success_log:
            logger.info("Action %s skipped by idempotency key", idempotency_key)
            return "success", "idempotent_skip"

        action_log = ActionLog.find_by_idempotency_key(idempotency_key)
        if action_log:
            doc_id = action_log["_id"]
            ActionLog.update(doc_id, status="pending", request_payload=decision.payload, error_message="")
        else:
            action_log = ActionLog.create(
                event_id=event_id,
                idempotency_key=idempotency_key,
                action_type=decision.action_type,
                status="pending",
                request_payload=decision.payload,
            )
            doc_id = action_log["_id"]

        validation_error = self._validate_action_payload(decision)
        if validation_error:
            ActionLog.update(doc_id, status="skipped", error_message=validation_error)
            return "skipped", validation_error

        if decision.action_type == "escalate":
            ActionLog.update(doc_id, status="success", response_payload={"note": "escalated to manual review queue"})
            return "success", ""

        if decision.action_type not in {"hide_comment", "reply_comment", "reply_message"}:
            error = f"unknown action: {decision.action_type}"
            ActionLog.update(doc_id, status="skipped", error_message=error)
            return "skipped", error

        retry_count = int(event.get("_retry_count", record.get("retry_count", 0) or 0) or 0)
        max_retries = int(event.get("_max_retries", 0) or 0) or None
        command = build_reply_command(event, decision, idempotency_key, retry_count=retry_count, max_retries=max_retries)

        try:
            result = self.reply_publisher.publish(command)
            ActionLog.update(
                doc_id,
                status="queued",
                request_payload=command,
                response_payload=result,
                error_message="",
            )
            return "queued", ""
        except ReplyCommandPublishError as exc:
            ActionLog.update(doc_id, status="failed", request_payload=command, error_message=str(exc))
            logger.error("Action %s queue failed for event %s: %s", decision.action_type, event_id[:8], exc)
            return "failed", str(exc)

    @staticmethod
    def _validate_action_payload(decision: ActionDecision) -> str:
        if decision.action_type == "hide_comment":
            return "" if decision.payload.get("comment_id") else "missing comment_id"
        if decision.action_type == "reply_comment":
            if decision.payload.get("comment_id") and decision.payload.get("message"):
                return ""
            return "missing comment_id or message"
        if decision.action_type == "reply_message":
            if decision.payload.get("page_id") and decision.payload.get("recipient_id") and decision.payload.get("message"):
                return ""
            return "missing page_id, recipient_id or message"
        return ""

    @staticmethod
    def _build_action_idempotency_key(event_id: str, decision: ActionDecision) -> str:
        event = {
            "event_id": event_id,
            "comment_id": decision.payload.get("comment_id", ""),
            "target_id": decision.payload.get("target_id", ""),
            "sender_id": decision.payload.get("recipient_id", ""),
        }
        target_id = (
            decision.payload.get("comment_id")
            or decision.payload.get("recipient_id")
            or decision.payload.get("target_id")
            or event_id
        )
        return build_command_id(event, action_type=decision.action_type, target_id=target_id)

    @staticmethod
    def _parse_datetime(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                normalized = value.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except (ValueError, TypeError):
                return None
        return None
