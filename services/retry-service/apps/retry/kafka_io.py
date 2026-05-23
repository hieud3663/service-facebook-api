"""Kafka input/output helpers for retry-service."""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class KafkaPublisher:
    def __init__(self):
        from kafka import KafkaProducer

        self._producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=True, default=str).encode("utf-8"),
            api_version_auto_timeout_ms=settings.KAFKA_API_VERSION_AUTO_TIMEOUT_MS,
        )

    def publish(self, topic: str, payload: dict) -> None:
        future = self._producer.send(topic, payload)
        future.get(timeout=10)
        self._producer.flush()

    def close(self) -> None:
        self._producer.close()


def create_consumer(topic: str):
    from kafka import KafkaConsumer

    return KafkaConsumer(
        topic,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP_ID,
        client_id=settings.KAFKA_CLIENT_ID,
        auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
        enable_auto_commit=False,
        value_deserializer=safe_json_deserializer,
        consumer_timeout_ms=settings.KAFKA_CONSUMER_TIMEOUT_MS,
        max_poll_records=settings.KAFKA_MAX_POLL_RECORDS,
        api_version_auto_timeout_ms=settings.KAFKA_API_VERSION_AUTO_TIMEOUT_MS,
    )


def safe_json_deserializer(message):
    """Return dict/list JSON payloads and let callers skip invalid records."""
    if message in (None, b""):
        logger.warning("Skipping empty Kafka message")
        return None
    try:
        decoded = message.decode("utf-8")
        if not decoded.strip():
            logger.warning("Skipping blank Kafka message")
            return None
        return json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Skipping non-JSON Kafka message: %s", exc)
        return None
