from django.test import SimpleTestCase

from apps.retry.backoff import calculate_backoff_seconds


class BackoffTests(SimpleTestCase):
    def test_exponential_backoff(self):
        self.assertEqual(calculate_backoff_seconds(0, 1, 60), 1)
        self.assertEqual(calculate_backoff_seconds(1, 1, 60), 2)
        self.assertEqual(calculate_backoff_seconds(2, 1, 60), 4)

    def test_respects_max_delay(self):
        self.assertEqual(calculate_backoff_seconds(10, 1, 60), 60)

