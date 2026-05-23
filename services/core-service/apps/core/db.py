"""
MongoDB connection singleton via pymongo.

Usage:
    from apps.core.db import get_db
    db = get_db()
    db.processed_events.insert_one({...})
"""
import logging
from datetime import timezone

from django.conf import settings
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        host = settings.MONGO_HOST
        port = settings.MONGO_PORT
        _client = MongoClient(host=host, port=port, serverSelectionTimeoutMS=5000, tz_aware=True, tzinfo=timezone.utc)
        logger.info("MongoDB connected: %s:%s", host, port)
    return _client


def get_db():
    """Return the default MongoDB database."""
    return get_client()[settings.MONGO_DB_NAME]


def ensure_indexes():
    """Create indexes on first startup."""
    db = get_db()

    # processed_events
    col = db.processed_events
    col.create_index("event_id", unique=True)
    col.create_index("platform_event_id")
    col.create_index("status")
    col.create_index("event_type")
    col.create_index("page_id")
    col.create_index("sender_id")
    col.create_index("message_hash")
    col.create_index([("sender_id", 1), ("message_hash", 1), ("created_at", DESCENDING)])
    col.create_index([("created_at", DESCENDING)])

    # action_logs
    col = db.action_logs
    col.create_index("event_id")
    col.create_index("idempotency_key", unique=True, sparse=True)
    col.create_index("action_type")
    col.create_index("status")

    # user_blacklist
    col = db.user_blacklist
    col.create_index("sender_id", unique=True)
    col.create_index("is_blacklisted")

    # manual_review_queue
    col = db.manual_review_queue
    col.create_index("event_id")
    col.create_index("status")
    col.create_index([("created_at", DESCENDING)])

    logger.info("MongoDB indexes ensured.")
