import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


class FacebookWebhookAPIViewTests(TestCase):
    def test_get_webhook_verification_success(self):
        url = reverse("facebook-webhook")

        with override_settings(FACEBOOK_WEBHOOK_VERIFY_TOKEN="verify-me"):
            response = self.client.get(
                url,
                {
                    "hub.mode": "subscribe",
                    "hub.verify_token": "verify-me",
                    "hub.challenge": "challenge-value",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "challenge-value")

    @override_settings(FACEBOOK_WEBHOOK_SECRET="my-secret")
    @patch("apps.webhook.views.KafkaRawEventPublisher.publish", return_value=1)
    def test_post_webhook_valid_signature(self, publish_mock):
        url = reverse("facebook-webhook")
        payload = {
            "object": "page",
            "entry": [{"id": "1", "changes": [], "messaging": []}],
        }
        raw = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"my-secret", raw, hashlib.sha256).hexdigest()

        response = self.client.post(
            url,
            data=raw,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )

        self.assertEqual(response.status_code, 202)
        publish_mock.assert_called_once()

    @patch(
        "apps.webhook.views.FacebookSubscriptionService.subscribe_page_comment_events",
        return_value={"success": True},
    )
    def test_subscribe_comment_events_success(self, subscribe_mock):
        url = reverse("facebook-comment-subscription")

        response = self.client.post(url, {"page_id": "123456"}, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "subscribed")
        subscribe_mock.assert_called_once_with(page_id="123456")

    def test_subscribe_comment_events_missing_page_id(self):
        url = reverse("facebook-comment-subscription")

        response = self.client.post(url, {}, content_type="application/json")

        self.assertEqual(response.status_code, 400)
