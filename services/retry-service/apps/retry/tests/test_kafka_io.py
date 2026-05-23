from django.test import SimpleTestCase

from apps.retry.kafka_io import safe_json_deserializer


class SafeJsonDeserializerTests(SimpleTestCase):
    def test_returns_none_for_empty_message(self):
        self.assertIsNone(safe_json_deserializer(b""))

    def test_returns_none_for_non_json_message(self):
        self.assertIsNone(safe_json_deserializer(b"not-json"))

    def test_returns_json_object(self):
        self.assertEqual(safe_json_deserializer(b'{"hello":"world"}'), {"hello": "world"})

