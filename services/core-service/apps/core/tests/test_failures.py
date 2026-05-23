from django.test import SimpleTestCase

from apps.core.failures import build_failure_payload, classify_failure


class FailurePayloadTests(SimpleTestCase):
    def test_classifies_timeout_as_retryable(self):
        failure_type, retryable = classify_failure("api-service timeout", 504)

        self.assertEqual(failure_type, "api_timeout")
        self.assertTrue(retryable)

    def test_classifies_permission_error_as_non_retryable(self):
        failure_type, retryable = classify_failure("forbidden", 403)

        self.assertEqual(failure_type, "permission_denied")
        self.assertFalse(retryable)

    def test_build_failure_payload_has_contract_fields(self):
        payload = build_failure_payload(
            {"event_id": "event-1", "comment_id": "comment-1", "page_id": "page-1"},
            {"error_message": "api-service timeout", "decision": "reply_comment"},
            retry_count=1,
            max_retries=3,
        )

        self.assertEqual(payload["event_id"], "event-1")
        self.assertEqual(payload["action_type"], "reply_comment")
        self.assertEqual(payload["target_id"], "comment-1")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["failure_type"], "api_timeout")
        self.assertIn("command_id", payload)

