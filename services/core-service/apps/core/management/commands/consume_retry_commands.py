"""Consume send_retry commands from retry-service and re-run core actions."""
import json
import logging
import signal
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.failures import build_failure_payload

logger = logging.getLogger(__name__)


def safe_json_deserializer(message):
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


class Command(BaseCommand):
    help = "Consume send_retry commands and retry core event processing."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        self.stdout.write(self.style.SUCCESS("Starting core send_retry consumer..."))
        self._run_consumer()

    def _signal_handler(self, signum, frame):
        self.stdout.write(self.style.WARNING(f"Received signal {signum}, shutting down gracefully..."))
        self._shutdown = True

    def _run_consumer(self):
        consumer, producer = self._connect_kafka(settings.KAFKA_SEND_RETRY_TOPIC)
        from apps.core.services import EventProcessor

        processor = EventProcessor()
        while not self._shutdown:
            try:
                messages = consumer.poll(timeout_ms=settings.KAFKA_POLL_TIMEOUT_MS)
                if not messages:
                    continue

                for _tp, records in messages.items():
                    for record in records:
                        command = record.value
                        if command is None:
                            logger.warning("Skipping invalid send_retry record at offset %s", record.offset)
                            continue
                        event = self._extract_event(command)
                        event["_retry_count"] = int(command.get("retry_count", 0) or 0)
                        event["_max_retries"] = int(command.get("max_retries", settings.KAFKA_MAX_RETRIES) or 0)
                        result = processor.process(event, force_retry=True)
                        if result.get("status") == "failed":
                            payload = build_failure_payload(
                                event,
                                result,
                                retry_count=int(command.get("retry_count", 0) or 0),
                                max_retries=int(command.get("max_retries", settings.KAFKA_MAX_RETRIES)),
                            )
                            self._publish(producer, settings.KAFKA_SEND_FAILED_TOPIC, payload)

                consumer.commit()
            except Exception as exc:
                logger.exception("Retry consumer loop error: %s", exc)
                time.sleep(2)

        consumer.close()
        producer.close()
        self.stdout.write(self.style.SUCCESS("Core send_retry consumer shut down."))

    @staticmethod
    def _extract_event(command: dict[str, Any]) -> dict[str, Any]:
        raw_event = command.get("raw_event") or command.get("event") or {}
        if raw_event:
            return raw_event
        payload = command.get("payload") or {}
        return {
            "event_id": command.get("event_id", ""),
            "event_type": payload.get("event_type", "comment"),
            "page_id": command.get("page_id", ""),
            "sender_id": payload.get("recipient_id", ""),
            "target_id": command.get("target_id", ""),
            "comment_id": payload.get("comment_id", command.get("target_id", "")),
            "message_text": payload.get("message", ""),
            "channel": payload.get("channel", ""),
            "raw_event": payload,
        }

    def _connect_kafka(self, topic: str):
        from kafka import KafkaConsumer, KafkaProducer
        from kafka.errors import KafkaError, NoBrokersAvailable

        attempt = 0
        while not self._shutdown:
            attempt += 1
            try:
                self.stdout.write(f"Connecting to Kafka {settings.KAFKA_BOOTSTRAP_SERVERS} (attempt {attempt})...")
                consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    group_id=f"{settings.KAFKA_CONSUMER_GROUP_ID}-retry",
                    client_id=f"{settings.KAFKA_CLIENT_ID}-retry",
                    auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
                    enable_auto_commit=False,
                    value_deserializer=safe_json_deserializer,
                    consumer_timeout_ms=settings.KAFKA_CONSUMER_TIMEOUT_MS,
                    max_poll_records=settings.KAFKA_MAX_POLL_RECORDS,
                    api_version_auto_timeout_ms=settings.KAFKA_API_VERSION_AUTO_TIMEOUT_MS,
                )
                producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v, ensure_ascii=True, default=str).encode("utf-8"),
                    api_version_auto_timeout_ms=settings.KAFKA_API_VERSION_AUTO_TIMEOUT_MS,
                )
                return consumer, producer
            except (NoBrokersAvailable, KafkaError) as exc:
                if settings.KAFKA_CONNECT_MAX_RETRIES and attempt >= settings.KAFKA_CONNECT_MAX_RETRIES:
                    raise
                logger.warning("Kafka broker is not ready (%s). Retrying...", exc)
                time.sleep(settings.KAFKA_CONNECT_BACKOFF_SECONDS)

        raise RuntimeError("Kafka consumer shutdown requested before connection was established")

    @staticmethod
    def _publish(producer, topic: str, payload: dict) -> None:
        future = producer.send(topic, payload)
        future.get(timeout=10)
        producer.flush()
