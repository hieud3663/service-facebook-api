"""Consume reply_commands and execute Facebook Graph API actions."""
import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.facebook_api.command_processor import ReplyCommandProcessor, ReplyCommandValidationError
from apps.facebook_api.kafka_io import KafkaPublisher, create_consumer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume reply_commands and execute Facebook actions."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        self.stdout.write(self.style.SUCCESS("Starting api-service reply_commands worker..."))
        self._run()

    def _signal_handler(self, signum, frame):
        self.stdout.write(self.style.WARNING(f"Received signal {signum}, shutting down gracefully..."))
        self._shutdown = True

    def _run(self):
        consumer = self._connect_consumer()
        publisher = KafkaPublisher()
        processor = ReplyCommandProcessor(publisher=publisher)

        while not self._shutdown:
            try:
                messages = consumer.poll(timeout_ms=settings.KAFKA_POLL_TIMEOUT_MS)
                if not messages:
                    continue

                for _tp, records in messages.items():
                    for record in records:
                        command = record.value
                        if command is None:
                            logger.warning("Skipping invalid reply_commands record at offset %s", record.offset)
                            continue
                        try:
                            result = processor.process(command)
                            logger.info("reply_commands result=%s command_id=%s", result.status, result.command_id)
                        except ReplyCommandValidationError as exc:
                            logger.error("Invalid reply command: %s", exc)
                        except Exception as exc:
                            logger.exception("Failed to process reply command: %s", exc)
                            raise

                consumer.commit()
            except Exception as exc:
                logger.exception("reply_commands worker loop error: %s", exc)
                time.sleep(2)

        consumer.close()
        publisher.close()
        self.stdout.write(self.style.SUCCESS("api-service reply_commands worker shut down."))

    def _connect_consumer(self):
        from kafka.errors import KafkaError, NoBrokersAvailable

        attempt = 0
        while not self._shutdown:
            attempt += 1
            try:
                self.stdout.write(f"Connecting to Kafka {settings.KAFKA_BOOTSTRAP_SERVERS} (attempt {attempt})...")
                return create_consumer(settings.KAFKA_REPLY_COMMANDS_TOPIC)
            except (NoBrokersAvailable, KafkaError) as exc:
                if settings.KAFKA_CONNECT_MAX_RETRIES and attempt >= settings.KAFKA_CONNECT_MAX_RETRIES:
                    raise
                logger.warning("Kafka broker is not ready (%s). Retrying...", exc)
                time.sleep(settings.KAFKA_CONNECT_BACKOFF_SECONDS)

        raise RuntimeError("api-service worker shutdown requested before connection was established")
