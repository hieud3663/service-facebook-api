from django.test import SimpleTestCase, override_settings

from apps.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from apps.core.clients import DifyAnalysisResult


class DifyAnalysisResultTests(SimpleTestCase):
    def test_parses_valid_json(self):
        raw = {
            "answer": (
                '{"intent":"praise","sentiment":"positive","is_spam":false,'
                '"is_malicious_link":false,"confidence":0.9,"reason":"nice"}'
            )
        }

        result = DifyAnalysisResult.from_dify_response(raw)

        self.assertEqual(result.intent, "praise")
        self.assertEqual(result.sentiment, "positive")
        self.assertEqual(result.confidence, 0.9)

    def test_invalid_json_returns_fallback(self):
        result = DifyAnalysisResult.from_dify_response({"answer": "not json"})

        self.assertEqual(result.intent, "unknown")
        self.assertEqual(result.sentiment, "neutral")
        self.assertTrue(result.parse_error)

    def test_out_of_whitelist_values_are_normalized(self):
        raw = {"answer": '{"intent":"other","sentiment":"angry","confidence":2}'}

        result = DifyAnalysisResult.from_dify_response(raw)

        self.assertEqual(result.intent, "unknown")
        self.assertEqual(result.sentiment, "neutral")
        self.assertEqual(result.confidence, 1.0)


class CircuitBreakerTests(SimpleTestCase):
    def test_opens_after_threshold(self):
        breaker = CircuitBreaker("test", failure_threshold=2, reset_timeout_seconds=30)

        with self.assertRaises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        with self.assertRaises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("boom")))

        with self.assertRaises(CircuitOpenError):
            breaker.call(lambda: "ok")

