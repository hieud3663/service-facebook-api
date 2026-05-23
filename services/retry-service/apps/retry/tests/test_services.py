from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.retry.services import RetryProcessor, RetryValidationError


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload):
        self.messages.append((topic, payload))


class RetryProcessorTests(SimpleTestCase):
    def setUp(self):
        self.publisher = FakePublisher()
        self.processor = RetryProcessor(self.publisher, sleep_func=lambda _delay: None)
        self.message = {
            "command_id": "event-1:reply_comment:comment-1",
            "event_id": "event-1",
            "action_type": "reply_comment",
            "target_id": "comment-1",
            "page_id": "page-1",
            "retry_count": 0,
            "max_retries": 3,
            "retryable": True,
            "failure_type": "api_timeout",
            "reason": "timeout",
            "payload": {"comment_id": "comment-1", "message": "hello"},
            "raw_event": {"event_id": "event-1"},
        }

    @override_settings(KAFKA_SEND_RETRY_TOPIC="send_retry")
    @patch("apps.retry.services.RetryAttempt.mark_scheduled")
    @patch("apps.retry.services.RetryAttempt.find_by_command_id", return_value=None)
    def test_retryable_message_is_scheduled(self, *_):
        result = self.processor.process(dict(self.message))

        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(self.publisher.messages[0][0], "send_retry")
        self.assertEqual(self.publisher.messages[0][1]["retry_count"], 1)

    @override_settings(KAFKA_DEAD_LETTER_TOPIC="dead_letter")
    @patch("apps.retry.services.RetryAttempt.mark_dead_lettered")
    @patch("apps.retry.services.RetryAttempt.find_by_command_id", return_value=None)
    def test_max_retry_goes_to_dead_letter(self, *_):
        message = dict(self.message, retry_count=3)

        result = self.processor.process(message)

        self.assertEqual(result["status"], "dead_lettered")
        self.assertEqual(self.publisher.messages[0][0], "dead_letter")

    @override_settings(KAFKA_DEAD_LETTER_TOPIC="dead_letter")
    @patch("apps.retry.services.RetryAttempt.mark_dead_lettered")
    @patch("apps.retry.services.RetryAttempt.find_by_command_id", return_value=None)
    def test_non_retryable_goes_to_dead_letter(self, *_):
        message = dict(self.message, retryable=False, failure_type="validation_error")

        result = self.processor.process(message)

        self.assertEqual(result["status"], "dead_lettered")
        self.assertEqual(self.publisher.messages[0][0], "dead_letter")

    @patch("apps.retry.services.RetryAttempt.find_by_command_id")
    def test_duplicate_retry_is_skipped(self, find_attempt):
        find_attempt.return_value = {"status": "scheduled", "scheduled_retry_counts": [1]}

        result = self.processor.process(dict(self.message))

        self.assertEqual(result["status"], "skipped")
        self.assertFalse(self.publisher.messages)

    def test_missing_identity_raises_validation_error(self):
        with self.assertRaises(RetryValidationError):
            self.processor.process({"retryable": True})

