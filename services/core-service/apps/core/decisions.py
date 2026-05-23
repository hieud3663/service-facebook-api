"""Decision engine: determines what action to take for each normalized event."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from django.conf import settings

from .clients import DifyAIClient, DifyAnalysisResult
from .models import ProcessedEvent, UserBlacklist
from .spam import LocalSpamDetector, SpamDetectionResult

logger = logging.getLogger(__name__)


@dataclass
class ActionDecision:
    action_type: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    should_execute: bool = True
    ai_result: DifyAnalysisResult | None = None
    spam_result: SpamDetectionResult | None = None


class DecisionEngine:
    """Run deterministic rules first, then AI, then map signals to actions."""

    BLACKLIST_STRIKE_LIMIT = 3
    BLACKLIST_WINDOW_HOURS = 24

    def __init__(self):
        self.ai_client = DifyAIClient()
        self.spam_detector = LocalSpamDetector()

    def decide(self, event: dict) -> ActionDecision:
        event_type = event.get("event_type", "unknown")
        message_text = event.get("message_text", "")
        sender_id = event.get("sender_id", "")
        page_id = event.get("page_id", "")
        meta = event.get("meta", {})

        if sender_id and page_id and sender_id == page_id:
            return ActionDecision(action_type="ignore", reason="page's own action", should_execute=False)

        if event_type == "unknown":
            return ActionDecision(action_type="ignore", reason="unsupported event type", should_execute=False)

        if event_type == "message" and meta.get("is_echo", False):
            return ActionDecision(action_type="ignore", reason="message echo", should_execute=False)

        verb = meta.get("verb", "add")
        if event_type == "comment" and verb not in ("add", ""):
            return ActionDecision(action_type="ignore", reason=f"verb={verb}, not 'add'", should_execute=False)

        if sender_id:
            entry = UserBlacklist.find_by_sender(sender_id)
            if entry and entry.get("is_blacklisted"):
                if event_type == "comment":
                    return ActionDecision(
                        action_type="hide_comment",
                        reason="sender is blacklisted",
                        payload={"comment_id": event.get("comment_id", "")},
                    )
                return ActionDecision(action_type="ignore", reason="sender is blacklisted", should_execute=False)

        if self._is_rate_limited(sender_id, page_id):
            return ActionDecision(
                action_type="escalate",
                reason="rate_limit_exceeded",
                payload={"sender_id": sender_id, "page_id": page_id},
            )

        spam_result = self.spam_detector.detect(message_text)
        ai_result = self.ai_client.analyze(message_text)

        is_malicious_link = spam_result.is_malicious_link or ai_result.is_malicious_link
        repeated_count = self._count_repeated_content(sender_id, spam_result.message_hash)
        is_repeated_spam = repeated_count >= self.BLACKLIST_STRIKE_LIMIT
        is_spam = spam_result.is_spam or ai_result.is_spam or is_repeated_spam

        if is_malicious_link:
            reason = "malicious link detected"
            if event_type == "comment":
                return ActionDecision(
                    action_type="hide_comment",
                    reason=reason,
                    payload={"comment_id": event.get("comment_id", ""), "escalate": True},
                    ai_result=ai_result,
                    spam_result=spam_result,
                )
            return ActionDecision(
                action_type="escalate",
                reason=reason,
                ai_result=ai_result,
                spam_result=spam_result,
            )

        if is_spam:
            self._record_spam_strike(sender_id, page_id)
            reason = "repeated spam detected" if is_repeated_spam else "spam detected"
            if event_type == "comment":
                return ActionDecision(
                    action_type="hide_comment",
                    reason=reason,
                    payload={"comment_id": event.get("comment_id", "")},
                    ai_result=ai_result,
                    spam_result=spam_result,
                )
            return ActionDecision(
                action_type="ignore",
                reason="spam message, no reply",
                should_execute=False,
                ai_result=ai_result,
                spam_result=spam_result,
            )

        if (
            ai_result.sentiment == "positive"
            and ai_result.confidence >= settings.CORE_AI_MIN_CONFIDENCE
            and settings.CORE_AUTO_REPLY_POSITIVE
        ):
            return self._reply_decision(
                event,
                sender_id,
                reason=f"positive sentiment, intent={ai_result.intent}",
                message=ai_result.reply_content or settings.CORE_POSITIVE_REPLY_MESSAGE,
                ai_result=ai_result,
                spam_result=spam_result,
            )

        if ai_result.sentiment == "negative":
            if (
                ai_result.confidence >= settings.CORE_AI_MIN_CONFIDENCE
                and settings.CORE_AUTO_REPLY_NEGATIVE
            ):
                return self._reply_decision(
                    event,
                    sender_id,
                    reason=f"negative sentiment auto reply, intent={ai_result.intent}",
                    message=ai_result.reply_content or settings.CORE_NEGATIVE_REPLY_MESSAGE,
                    ai_result=ai_result,
                    spam_result=spam_result,
                    escalate=True,
                )
            return ActionDecision(
                action_type="escalate",
                reason=f"negative sentiment, intent={ai_result.intent}",
                ai_result=ai_result,
                spam_result=spam_result,
            )

        if ai_result.reply_content and ai_result.confidence >= settings.CORE_AI_MIN_CONFIDENCE:
            return self._reply_decision(
                event,
                sender_id,
                reason=f"AI generated reply, intent={ai_result.intent}",
                message=ai_result.reply_content,
                ai_result=ai_result,
                spam_result=spam_result,
            )

        return ActionDecision(
            action_type="ignore",
            reason=f"normal event, intent={ai_result.intent}, sentiment={ai_result.sentiment}",
            should_execute=False,
            ai_result=ai_result,
            spam_result=spam_result,
        )

    def _reply_decision(
        self,
        event: dict,
        sender_id: str,
        reason: str,
        message: str,
        ai_result: DifyAnalysisResult,
        spam_result: SpamDetectionResult,
        escalate: bool = False,
    ) -> ActionDecision:
        event_type = event.get("event_type", "unknown")
        if event_type == "comment":
            payload: dict[str, Any] = {
                "comment_id": event.get("comment_id", ""),
                "message": message,
            }
            if escalate:
                payload["escalate"] = True
            return ActionDecision(
                action_type="reply_comment",
                reason=reason,
                payload=payload,
                ai_result=ai_result,
                spam_result=spam_result,
            )

        if event_type == "message":
            payload = {
                "page_id": event.get("page_id", ""),
                "recipient_id": sender_id,
                "message": message,
            }
            if escalate:
                payload["escalate"] = True
            return ActionDecision(
                action_type="reply_message",
                reason=reason,
                payload=payload,
                ai_result=ai_result,
                spam_result=spam_result,
            )

        return ActionDecision(
            action_type="escalate" if escalate else "ignore",
            reason=reason,
            should_execute=escalate,
            ai_result=ai_result,
            spam_result=spam_result,
        )

    def _is_rate_limited(self, sender_id: str, page_id: str) -> bool:
        if not sender_id or not page_id:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.CORE_RATE_LIMIT_WINDOW_SECONDS)
        try:
            count = ProcessedEvent.count_recent_by_sender(sender_id, page_id, cutoff)
        except Exception as exc:
            logger.warning("Failed to count recent events for sender %s: %s", sender_id, exc)
            return False
        return count >= settings.CORE_RATE_LIMIT_MAX_EVENTS

    def _count_repeated_content(self, sender_id: str, message_hash: str) -> int:
        if not sender_id or not message_hash:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.BLACKLIST_WINDOW_HOURS)
        try:
            return ProcessedEvent._col().count_documents(
                {
                    "sender_id": sender_id,
                    "message_hash": message_hash,
                    "created_at": {"$gte": cutoff},
                }
            )
        except Exception as exc:
            logger.warning("Failed to count repeated content for sender %s: %s", sender_id, exc)
            return 0

    def _record_spam_strike(self, sender_id: str, page_id: str) -> None:
        if not sender_id:
            return

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.BLACKLIST_WINDOW_HOURS)
        entry = UserBlacklist.find_by_sender(sender_id)

        if entry is None:
            UserBlacklist.upsert(
                sender_id,
                page_id=page_id,
                spam_count_24h=1,
                last_spam_at=now,
                is_blacklisted=False,
                reason="",
            )
            return

        spam_count = entry.get("spam_count_24h", 0)
        last_spam_at = self._as_aware_utc(entry.get("last_spam_at"))
        if last_spam_at and last_spam_at < cutoff:
            spam_count = 0

        spam_count += 1
        is_blacklisted = spam_count >= self.BLACKLIST_STRIKE_LIMIT
        reason = f"Auto-blacklisted: {spam_count} spam strikes in 24h" if is_blacklisted else ""

        if is_blacklisted:
            logger.warning("User %s auto-blacklisted after %d spam strikes", sender_id, spam_count)

        UserBlacklist.upsert(
            sender_id,
            page_id=page_id,
            spam_count_24h=spam_count,
            last_spam_at=now,
            is_blacklisted=is_blacklisted,
            reason=reason,
        )

    @staticmethod
    def _as_aware_utc(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

