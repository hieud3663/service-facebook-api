import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.webhook.services import (
    FacebookEventNormalizer,
    FacebookWebhookVerifier,
    WebhookSignatureError,
)


class FacebookWebhookVerifierTests(SimpleTestCase):
    @override_settings(FACEBOOK_WEBHOOK_SECRET="my-secret")
    def test_verify_signature_success(self):
        body = json.dumps({"hello": "world"}).encode("utf-8")
        signature = hmac.new(b"my-secret", body, hashlib.sha256).hexdigest()

        FacebookWebhookVerifier.verify_signature(body, f"sha256={signature}")

    @override_settings(FACEBOOK_WEBHOOK_SECRET="my-secret")
    def test_verify_signature_invalid(self):
        body = b"{}"

        with self.assertRaises(WebhookSignatureError):
            FacebookWebhookVerifier.verify_signature(body, "sha256=invalid")


class FacebookEventNormalizerTests(SimpleTestCase):
    def test_normalize_comment_and_message_payload(self):
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "123",
                    "changes": [
                        {
                            "field": "feed",
                            "value": {
                                "item": "comment",
                                "verb": "add",
                                "created_time": 1700000000000,
                                "post_id": "123_456",
                                "comment_id": "789",
                                "from": {"id": "42", "name": "Alice"},
                            },
                        }
                    ],
                    "messaging": [
                        {
                            "sender": {"id": "1001"},
                            "recipient": {"id": "123"},
                            "timestamp": 1700000000000,
                            "message": {
                                "mid": "m_abc",
                                "text": "hello",
                            },
                        }
                    ],
                }
            ],
        }

        events = FacebookEventNormalizer.normalize(payload)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "comment")
        self.assertEqual(events[0]["page_id"], "123")
        self.assertEqual(events[1]["event_type"], "message")
        self.assertEqual(events[1]["channel"], "facebook_messenger")

    @patch("apps.webhook.services.uuid.uuid4", return_value="fixed-uuid")
    def test_normalize_contains_stable_shape(self, _):
        payload = {
            "object": "page",
            "entry": [{"id": "123", "changes": [], "messaging": []}],
        }

        events = FacebookEventNormalizer.normalize(payload)

        self.assertEqual(events, [])
