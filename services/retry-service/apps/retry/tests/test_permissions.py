from django.test import TestCase, override_settings
from django.urls import reverse


class RetryPermissionTests(TestCase):
    def test_health_is_public(self):
        response = self.client.get(reverse("retry-health"))

        self.assertEqual(response.status_code, 200)

    @override_settings(RETRY_INTERNAL_API_KEY="secret")
    def test_attempts_requires_internal_key(self):
        response = self.client.get(reverse("retry-attempts"))

        self.assertEqual(response.status_code, 403)

