"""
MongoDB document helpers (pymongo-based, no Django ORM).

Each class wraps a MongoDB collection with typed insert/query/update methods.
"""
from datetime import datetime, timezone
from typing import Any

from .db import get_db


class ProcessedEvent:
    """Collection: processed_events"""

    COLLECTION = "processed_events"

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, **fields) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            "event_id": fields.get("event_id", ""),
            "platform_event_id": fields.get("platform_event_id", ""),
            "source": fields.get("source", "facebook"),
            "event_type": fields.get("event_type", "unknown"),
            "channel": fields.get("channel", ""),
            "page_id": fields.get("page_id", ""),
            "sender_id": fields.get("sender_id", ""),
            "actor_name": fields.get("actor_name", ""),
            "target_id": fields.get("target_id", ""),
            "post_id": fields.get("post_id", ""),
            "comment_id": fields.get("comment_id", ""),
            "parent_id": fields.get("parent_id", ""),
            "message_text": fields.get("message_text", ""),
            "message_hash": fields.get("message_hash", ""),
            "intent": fields.get("intent", ""),
            "sentiment": fields.get("sentiment", ""),
            "is_spam": fields.get("is_spam", False),
            "is_malicious_link": fields.get("is_malicious_link", False),
            "ai_confidence": fields.get("ai_confidence", 0.0),
            "ai_reason": fields.get("ai_reason", ""),
            "ai_parse_error": fields.get("ai_parse_error", ""),
            "ai_raw_response": fields.get("ai_raw_response", {}),
            "spam_score": fields.get("spam_score", 0),
            "spam_signals": fields.get("spam_signals", []),
            "spam_reason": fields.get("spam_reason", ""),
            "detected_links": fields.get("detected_links", []),
            "status": fields.get("status", "received"),
            "decision": fields.get("decision", ""),
            "decision_reason": fields.get("decision_reason", ""),
            "raw_event": fields.get("raw_event", {}),
            "error_message": fields.get("error_message", ""),
            "retry_count": fields.get("retry_count", 0),
            "last_failed_at": fields.get("last_failed_at"),
            "occurred_at": fields.get("occurred_at"),
            "created_at": now,
            "updated_at": now,
        }
        cls._col().insert_one(doc)
        return doc

    @classmethod
    def find_by_event_id(cls, event_id: str) -> dict | None:
        return cls._col().find_one({"event_id": event_id})

    @classmethod
    def update_by_event_id(cls, event_id: str, **fields) -> None:
        fields["updated_at"] = datetime.now(timezone.utc)
        cls._col().update_one({"event_id": event_id}, {"$set": fields})

    @classmethod
    def list_events(cls, filters: dict | None = None, limit: int = 50) -> list[dict]:
        q = filters or {}
        return list(cls._col().find(q).sort("created_at", -1).limit(limit))

    @classmethod
    def count_recent_by_sender(cls, sender_id: str, page_id: str, since: datetime) -> int:
        if not sender_id or not page_id:
            return 0
        return cls._col().count_documents(
            {
                "sender_id": sender_id,
                "page_id": page_id,
                "created_at": {"$gte": since},
            }
        )

    @classmethod
    def count_by_status(cls) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in cls._col().aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
            counts[row.get("_id") or "unknown"] = row.get("count", 0)
        return counts

    @classmethod
    def delete_by_event_id(cls, event_id: str) -> None:
        cls._col().delete_one({"event_id": event_id})


class ActionLog:
    """Collection: action_logs"""

    COLLECTION = "action_logs"

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, **fields) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            "event_id": fields.get("event_id", ""),
            "idempotency_key": fields.get("idempotency_key", ""),
            "action_type": fields.get("action_type", ""),
            "status": fields.get("status", "pending"),
            "request_payload": fields.get("request_payload", {}),
            "response_payload": fields.get("response_payload", {}),
            "error_message": fields.get("error_message", ""),
            "attempt": fields.get("attempt", 0),
            "created_at": now,
            "updated_at": now,
        }
        result = cls._col().insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    @classmethod
    def update(cls, doc_id, **fields) -> None:
        fields["updated_at"] = datetime.now(timezone.utc)
        cls._col().update_one({"_id": doc_id}, {"$set": fields})

    @classmethod
    def find_by_event_id(cls, event_id: str) -> list[dict]:
        return list(cls._col().find({"event_id": event_id}).sort("created_at", -1))

    @classmethod
    def find_by_idempotency_key(cls, idempotency_key: str) -> dict | None:
        if not idempotency_key:
            return None
        return cls._col().find_one({"idempotency_key": idempotency_key}, sort=[("created_at", -1)])

    @classmethod
    def find_success_by_idempotency_key(cls, idempotency_key: str) -> dict | None:
        if not idempotency_key:
            return None
        return cls._col().find_one(
            {"idempotency_key": idempotency_key, "status": "success"},
            sort=[("created_at", -1)],
        )


class UserBlacklist:
    """Collection: user_blacklist"""

    COLLECTION = "user_blacklist"

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_by_sender(cls, sender_id: str) -> dict | None:
        return cls._col().find_one({"sender_id": sender_id})

    @classmethod
    def upsert(cls, sender_id: str, **fields) -> None:
        fields["updated_at"] = datetime.now(timezone.utc)
        cls._col().update_one(
            {"sender_id": sender_id},
            {"$set": fields, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )


class ManualReviewQueue:
    """Collection: manual_review_queue"""

    COLLECTION = "manual_review_queue"

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, **fields) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            "event_id": fields.get("event_id", ""),
            "reason": fields.get("reason", ""),
            "status": fields.get("status", "pending_review"),
            "reviewer_note": fields.get("reviewer_note", ""),
            "created_at": now,
            "updated_at": now,
        }
        cls._col().insert_one(doc)
        return doc

    @classmethod
    def list_pending(cls, limit: int = 50) -> list[dict]:
        return list(cls._col().find({"status": "pending_review"}).sort("created_at", -1).limit(limit))
