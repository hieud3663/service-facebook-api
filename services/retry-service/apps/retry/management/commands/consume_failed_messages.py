"""Consume send_failed and publish send_retry or dead_letter."""
import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.retry.kafka_io import KafkaPublisher, create_consumer
from apps.retry.services import RetryProcessor, RetryValidationError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume send_failed messages and schedule retries."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        self.stdout.write(self.style.SUCCESS("Starting retry-service worker..."))
        self._run()

    def _signal_handler(self, signum, frame):
        self.stdout.write(self.style.WARNING(f"Received signal {signum}, shutting down gracefully..."))
        self._shutdown = True

    def _run(self):
        consumer = self._connect_consumer()
        publisher = KafkaPublisher()
        processor = RetryProcessor(publisher=publisher)

        while not self._shutdown:
            try:
                messages = consumer.poll(timeout_ms=settings.KAFKA_POLL_TIMEOUT_MS)
                if not messages:
                    continue

                total_records = sum(len(records) for records in messages.values())
                logger.info("Polled %d send_failed records", total_records)
                for _tp, records in messages.items():
                    for record in records:
                        if record.value is None:
                            logger.warning("Skipping invalid send_failed record at offset %s", record.offset)
                            continue
                        try:
                            logger.info(
                                "Consuming send_failed offset=%s command_id=%s event_id=%s",
                                record.offset,
                                record.value.get("command_id", ""),
                                record.value.get("event_id", ""),
                            )
                            result = processor.process(record.value)
                            logger.info("Retry processor result: %s", result.get("status"))
                        except RetryValidationError as exc:
                            logger.error("Invalid send_failed message: %s", exc)
                        except Exception as exc:
                            logger.exception("Failed to process retry message: %s", exc)
                            raise

                consumer.commit()
            except Exception as exc:
                logger.exception("Retry worker loop error: %s", exc)
                time.sleep(2)

        consumer.close()
        publisher.close()
        self.stdout.write(self.style.SUCCESS("Retry-service worker shut down."))

    def _connect_consumer(self):
        from kafka.errors import KafkaError, NoBrokersAvailable

        attempt = 0
        while not self._shutdown:
            attempt += 1
            try:
                self.stdout.write(f"Connecting to Kafka {settings.KAFKA_BOOTSTRAP_SERVERS} (attempt {attempt})...")
                return create_consumer(settings.KAFKA_SEND_FAILED_TOPIC)
            except (NoBrokersAvailable, KafkaError) as exc:
                if settings.KAFKA_CONNECT_MAX_RETRIES and attempt >= settings.KAFKA_CONNECT_MAX_RETRIES:
                    raise
                logger.warning("Kafka broker is not ready (%s). Retrying...", exc)
                time.sleep(settings.KAFKA_CONNECT_BACKOFF_SECONDS)

        raise RuntimeError("Retry worker shutdown requested before connection was established")
