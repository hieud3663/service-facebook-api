"""MongoDB connection helpers for retry-service."""
import logging
from datetime import timezone

from django.conf import settings
from pymongo import ASCENDING, DESCENDING, MongoClient

logger = logging.getLogger(__name__)

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            host=settings.MONGO_HOST,
            port=settings.MONGO_PORT,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
            tzinfo=timezone.utc,
        )
        logger.info("MongoDB connected: %s:%s", settings.MONGO_HOST, settings.MONGO_PORT)
    return _client


def get_db():
    return get_client()[settings.MONGO_DB_NAME]


def ensure_indexes():
    col = get_db().retry_attempts
    col.create_index("command_id", unique=True)
    col.create_index("status")
    col.create_index([("updated_at", DESCENDING)])
    col.create_index([("event_id", ASCENDING), ("action_type", ASCENDING)])
    logger.info("Retry service MongoDB indexes ensured.")

