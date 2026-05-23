from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.decisions import ActionDecision
from apps.core.services import EventProcessor


class FakeReplyPublisher:
    def __init__(self):
        self.commands = []

    def publish(self, command):
        self.commands.append(command)
        return {"topic": "reply_commands", "queued_at": command["queued_at"]}


class EventProcessorActionIdempotencyTests(SimpleTestCase):
    def setUp(self):
        self.publisher = FakeReplyPublisher()
        self.processor = EventProcessor(reply_publisher=self.publisher)

    @patch("apps.core.services.ActionLog.find_success_by_idempotency_key")
    def test_successful_existing_action_is_not_queued_again(self, find_success):
        find_success.return_value = {"status": "success"}
        decision = ActionDecision(
            action_type="reply_comment",
            reason="test",
            payload={"comment_id": "c1", "message": "hello"},
        )

        status, error = self.processor._execute_action({"event_id": "event-1"}, {}, decision)

        self.assertEqual(status, "success")
        self.assertEqual(error, "idempotent_skip")
        self.assertEqual(self.publisher.commands, [])

    @patch("apps.core.services.ActionLog.update")
    @patch("apps.core.services.ActionLog.create")
    @patch("apps.core.services.ActionLog.find_by_idempotency_key", return_value=None)
    @patch("apps.core.services.ActionLog.find_success_by_idempotency_key", return_value=None)
    def test_reply_comment_publishes_reply_command(self, *_mocks):
        create_mock = _mocks[2]
        update_mock = _mocks[3]
        create_mock.return_value = {"_id": "log-1"}
        decision = ActionDecision(
            action_type="reply_comment",
            reason="test",
            payload={"comment_id": "c1", "message": "hello"},
        )

        status, error = self.processor._execute_action(
            {"event_id": "event-1", "page_id": "page-1"},
            {"retry_count": 0},
            decision,
        )

        self.assertEqual(status, "queued")
        self.assertEqual(error, "")
        self.assertEqual(len(self.publisher.commands), 1)
        command = self.publisher.commands[0]
        self.assertEqual(command["command_id"], "event-1:reply_comment:c1")
        self.assertEqual(command["action_type"], "reply_comment")
        self.assertEqual(command["payload"]["message"], "hello")
        self.assertEqual(command["page_id"], "page-1")
        update_mock.assert_called()

    @patch("apps.core.services.ActionLog.update")
    @patch("apps.core.services.ActionLog.create")
    @patch("apps.core.services.ActionLog.find_by_idempotency_key", return_value=None)
    @patch("apps.core.services.ActionLog.find_success_by_idempotency_key", return_value=None)
    def test_invalid_reply_comment_is_skipped(self, *_mocks):
        create_mock = _mocks[2]
        create_mock.return_value = {"_id": "log-1"}
        decision = ActionDecision(
            action_type="reply_comment",
            reason="test",
            payload={"comment_id": "c1"},
        )

        status, error = self.processor._execute_action({"event_id": "event-1"}, {}, decision)

        self.assertEqual(status, "skipped")
        self.assertEqual(error, "missing comment_id or message")
        self.assertEqual(self.publisher.commands, [])
