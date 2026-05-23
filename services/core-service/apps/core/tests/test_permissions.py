from django.test import TestCase, override_settings
from django.urls import reverse


class CorePermissionTests(TestCase):
    def test_health_is_public(self):
        response = self.client.get(reverse("core-health"))

        self.assertEqual(response.status_code, 200)

    @override_settings(CORE_INTERNAL_API_KEY="secret")
    def test_events_requires_internal_key(self):
        response = self.client.get(reverse("core-events"))

        self.assertEqual(response.status_code, 403)

