"""Consume raw_events and hand retryable failures to retry-service."""
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
    help = "Consume raw_events from Kafka and process them through the Core pipeline."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        self.stdout.write(self.style.SUCCESS("Starting core raw_events consumer..."))
        self._run_consumer()

    def _signal_handler(self, signum, frame):
        self.stdout.write(self.style.WARNING(f"Received signal {signum}, shutting down gracefully..."))
        self._shutdown = True

    def _run_consumer(self):
        consumer, producer = self._connect_kafka(settings.KAFKA_RAW_EVENTS_TOPIC)
        self.stdout.write(self.style.SUCCESS(f"Subscribed to topic: {settings.KAFKA_RAW_EVENTS_TOPIC}"))

        from apps.core.services import EventProcessor

        processor = EventProcessor()
        while not self._shutdown:
            try:
                messages = consumer.poll(timeout_ms=settings.KAFKA_POLL_TIMEOUT_MS)
                if not messages:
                    continue

                for _tp, records in messages.items():
                    for record in records:
                        event = record.value
                        if event is None:
                            logger.warning("Skipping invalid raw_events record at offset %s", record.offset)
                            continue
                        success, result = self._process_with_fast_retry(processor, event)
                        if not success:
                            payload = build_failure_payload(
                                event,
                                result,
                                retry_count=int(result.get("retry_count", 0) or 0),
                                max_retries=settings.KAFKA_MAX_RETRIES,
                            )
                            self._publish(producer, settings.KAFKA_SEND_FAILED_TOPIC, payload)

                consumer.commit()
            except Exception as exc:
                logger.exception("Consumer loop error: %s", exc)
                time.sleep(2)

        consumer.close()
        producer.close()
        self.stdout.write(self.style.SUCCESS("Core raw_events consumer shut down."))

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
                    group_id=settings.KAFKA_CONSUMER_GROUP_ID,
                    client_id=settings.KAFKA_CLIENT_ID,
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

    def _process_with_fast_retry(self, processor, event: dict[str, Any]) -> tuple[bool, dict]:
        from apps.core.models import ProcessedEvent

        last_result: dict[str, Any] = {}
        attempts = max(0, settings.KAFKA_CONSUMER_FAST_RETRIES) + 1
        event_id = event.get("event_id", "")

        for attempt in range(attempts):
            try:
                result = processor.process(event, force_retry=attempt > 0)
                last_result = result if isinstance(result, dict) else {}
                if last_result.get("status") != "failed":
                    return True, last_result
            except Exception as exc:
                logger.exception("Unhandled error processing event %s", event_id[:8])
                last_result = {"status": "failed", "error_message": str(exc)}

            if attempt < attempts - 1:
                retry_count = attempt + 1
                if event_id:
                    ProcessedEvent.update_by_event_id(
                        event_id,
                        status="retrying",
                        retry_count=retry_count,
                        error_message=last_result.get("error_message", ""),
                    )
                time.sleep(min(2 ** attempt, 5))

        if event_id:
            ProcessedEvent.update_by_event_id(
                event_id,
                status="send_failed",
                retry_count=max(0, attempts - 1),
                error_message=last_result.get("error_message", "processing failed"),
            )
        last_result["status"] = "send_failed"
        last_result["retry_count"] = max(0, attempts - 1)
        return False, last_result

    @staticmethod
    def _publish(producer, topic: str, payload: dict) -> None:
        future = producer.send(topic, payload)
        future.get(timeout=10)
        producer.flush()
        logger.warning("Published failure for event %s to %s", payload.get("event_id", "")[:8], topic)
