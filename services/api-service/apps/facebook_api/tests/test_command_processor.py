from django.test import SimpleTestCase, override_settings

from apps.facebook_api.command_processor import (
    ReplyCommandProcessor,
    ReplyCommandValidationError,
    classify_facebook_failure,
)
from apps.facebook_api.services import FacebookServiceError


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload):
        self.messages.append((topic, payload))


class FakeFacebookService:
    def __init__(self, response=None, error=None):
        self.response = response or {"id": "ok"}
        self.error = error
        self.calls = []

    def reply_comment(self, comment_id, message):
        self.calls.append(("reply_comment", comment_id, message))
        if self.error:
            raise self.error
        return self.response

    def hide_comment(self, comment_id, is_hidden=True):
        self.calls.append(("hide_comment", comment_id, is_hidden))
        if self.error:
            raise self.error
        return self.response

    def send_message(self, recipient_id, message):
        self.calls.append(("send_message", recipient_id, message))
        if self.error:
            raise self.error
        return self.response


@override_settings(KAFKA_SEND_FAILED_TOPIC="send_failed", KAFKA_MAX_RETRIES=3)
class ReplyCommandProcessorTests(SimpleTestCase):
    def test_executes_reply_comment_command(self):
        publisher = FakePublisher()
        service = FakeFacebookService(response={"id": "reply-1"})
        processor = ReplyCommandProcessor(publisher=publisher, service=service)

        result = processor.process(
            {
                "command_id": "event-1:reply_comment:c1",
                "event_id": "event-1",
                "action_type": "reply_comment",
                "target_id": "c1",
                "payload": {"comment_id": "c1", "message": "hello"},
            }
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(service.calls, [("reply_comment", "c1", "hello")])
        self.assertEqual(publisher.messages, [])

    def test_facebook_error_is_published_to_send_failed(self):
        publisher = FakePublisher()
        service = FakeFacebookService(error=FacebookServiceError("temporarily unavailable", status_code=503))
        processor = ReplyCommandProcessor(publisher=publisher, service=service)

        result = processor.process(
            {
                "command_id": "event-1:reply_comment:c1",
                "event_id": "event-1",
                "action_type": "reply_comment",
                "target_id": "c1",
                "retry_count": 1,
                "max_retries": 3,
                "payload": {"comment_id": "c1", "message": "hello"},
                "raw_event": {"event_id": "event-1"},
            }
        )

        self.assertEqual(result.status, "failed_published")
        self.assertEqual(len(publisher.messages), 1)
        topic, payload = publisher.messages[0]
        self.assertEqual(topic, "send_failed")
        self.assertEqual(payload["command_id"], "event-1:reply_comment:c1")
        self.assertEqual(payload["failure_type"], "api_5xx")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["retry_count"], 1)

    def test_invalid_command_raises_validation_error(self):
        processor = ReplyCommandProcessor(publisher=FakePublisher(), service=FakeFacebookService())

        with self.assertRaises(ReplyCommandValidationError):
            processor.process({"command_id": "bad", "event_id": "event-1", "action_type": "reply_comment"})

    def test_classifies_permission_as_non_retryable(self):
        failure_type, retryable = classify_facebook_failure("permission denied", 403)

        self.assertEqual(failure_type, "permission_denied")
        self.assertFalse(retryable)
