"""Pymongo document helpers for retry-service."""
from datetime import datetime, timezone

from .db import get_db


class RetryAttempt:
    COLLECTION = "retry_attempts"

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_by_command_id(cls, command_id: str) -> dict | None:
        return cls._col().find_one({"command_id": command_id})

    @classmethod
    def mark_scheduled(cls, message: dict, retry_count: int, next_retry_at) -> dict:
        now = datetime.now(timezone.utc)
        command_id = message["command_id"]
        update = {
            "$set": {
                "command_id": command_id,
                "event_id": message.get("event_id", ""),
                "action_type": message.get("action_type", ""),
                "target_id": message.get("target_id", ""),
                "status": "scheduled",
                "retry_count": retry_count,
                "last_failure_type": message.get("failure_type", ""),
                "last_reason": message.get("reason", ""),
                "next_retry_at": next_retry_at,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
            "$addToSet": {"scheduled_retry_counts": retry_count},
        }
        cls._col().update_one({"command_id": command_id}, update, upsert=True)
        return cls.find_by_command_id(command_id) or {}

    @classmethod
    def mark_dead_lettered(cls, message: dict, retry_count: int, reason: str) -> dict:
        now = datetime.now(timezone.utc)
        command_id = message["command_id"]
        update = {
            "$set": {
                "command_id": command_id,
                "event_id": message.get("event_id", ""),
                "action_type": message.get("action_type", ""),
                "target_id": message.get("target_id", ""),
                "status": "dead_lettered",
                "retry_count": retry_count,
                "last_failure_type": message.get("failure_type", ""),
                "last_reason": reason,
                "dead_lettered_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        }
        cls._col().update_one({"command_id": command_id}, update, upsert=True)
        return cls.find_by_command_id(command_id) or {}

    @classmethod
    def list_attempts(cls, filters: dict | None = None, limit: int = 50) -> list[dict]:
        return list(cls._col().find(filters or {}).sort("updated_at", -1).limit(limit))

    @classmethod
    def count_by_status(cls) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in cls._col().aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
            counts[row.get("_id") or "unknown"] = row.get("count", 0)
        return counts

