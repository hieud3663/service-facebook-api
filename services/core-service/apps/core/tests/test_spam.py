from django.test import SimpleTestCase

from apps.core.spam import LocalSpamDetector


class LocalSpamDetectorTests(SimpleTestCase):
    def setUp(self):
        self.detector = LocalSpamDetector()

    def test_detects_suspicious_short_link_as_malicious(self):
        result = self.detector.detect("click here https://bit.ly/win-now")

        self.assertTrue(result.is_spam)
        self.assertTrue(result.is_malicious_link)
        self.assertIn("suspicious_short_link", result.signals)

    def test_detects_scam_keyword(self):
        result = self.detector.detect("free money click here casino now")

        self.assertTrue(result.is_spam)
        self.assertIn("scam_keyword", result.signals)

    def test_empty_text_is_not_spam(self):
        result = self.detector.detect("")

        self.assertFalse(result.is_spam)
        self.assertEqual(result.message_hash, "")
