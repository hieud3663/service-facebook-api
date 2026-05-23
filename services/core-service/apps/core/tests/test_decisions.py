from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.core.clients import DifyAnalysisResult
from apps.core.decisions import DecisionEngine
from apps.core.spam import SpamDetectionResult


class DecisionEngineTests(SimpleTestCase):
    def setUp(self):
        self.engine = DecisionEngine()
        self.engine.ai_client = Mock()
        self.engine.spam_detector = Mock()
        self.engine.spam_detector.detect.return_value = SpamDetectionResult(message_hash="hash")
        self.engine._count_repeated_content = Mock(return_value=0)
        self.engine._record_spam_strike = Mock()

    @patch("apps.core.decisions.UserBlacklist.find_by_sender", return_value=None)
    def test_unknown_event_is_ignored(self, _):
        decision = self.engine.decide({"event_type": "unknown"})

        self.assertEqual(decision.action_type, "ignore")
        self.assertFalse(decision.should_execute)

    @patch("apps.core.decisions.UserBlacklist.find_by_sender", return_value=None)
    def test_message_echo_is_ignored(self, _):
        decision = self.engine.decide({"event_type": "message", "meta": {"is_echo": True}})

        self.assertEqual(decision.action_type, "ignore")
        self.assertFalse(decision.should_execute)

    @patch("apps.core.decisions.ProcessedEvent.count_recent_by_sender", return_value=0)
    @patch("apps.core.decisions.UserBlacklist.find_by_sender", return_value=None)
    def test_spam_comment_hides_comment(self, *_):
        self.engine.spam_detector.detect.return_value = SpamDetectionResult(
            is_spam=True,
            score=3,
            message_hash="hash",
        )
        self.engine.ai_client.analyze.return_value = DifyAnalysisResult()

        decision = self.engine.decide(
            {
                "event_type": "comment",
                "sender_id": "user-1",
                "page_id": "page-1",
                "comment_id": "comment-1",
            }
        )

        self.assertEqual(decision.action_type, "hide_comment")
        self.assertEqual(decision.payload["comment_id"], "comment-1")

    @override_settings(CORE_RATE_LIMIT_MAX_EVENTS=20, CORE_RATE_LIMIT_WINDOW_SECONDS=60)
    @patch("apps.core.decisions.ProcessedEvent.count_recent_by_sender", return_value=20)
    @patch("apps.core.decisions.UserBlacklist.find_by_sender", return_value=None)
    def test_rate_limited_sender_goes_to_review(self, *_):
        decision = self.engine.decide(
            {
                "event_type": "comment",
                "sender_id": "user-1",
                "page_id": "page-1",
                "comment_id": "comment-1",
            }
        )

        self.assertEqual(decision.action_type, "escalate")
        self.assertEqual(decision.reason, "rate_limit_exceeded")
        self.engine.ai_client.analyze.assert_not_called()

    @override_settings(CORE_AUTO_REPLY_POSITIVE=True, CORE_AI_MIN_CONFIDENCE=0.6)
    @patch("apps.core.decisions.ProcessedEvent.count_recent_by_sender", return_value=0)
    @patch("apps.core.decisions.UserBlacklist.find_by_sender", return_value=None)
    def test_positive_comment_gets_thank_you_reply(self, *_):
        self.engine.ai_client.analyze.return_value = DifyAnalysisResult(
            intent="praise",
            sentiment="positive",
            confidence=0.9,
        )

        decision = self.engine.decide(
            {
                "event_type": "comment",
                "sender_id": "user-1",
                "page_id": "page-1",
                "comment_id": "comment-1",
                "message_text": "great",
            }
        )

        self.assertEqual(decision.action_type, "reply_comment")
        self.assertIn("message", decision.payload)

    @override_settings(CORE_AUTO_REPLY_NEGATIVE=True, CORE_AI_MIN_CONFIDENCE=0.6)
    @patch("apps.core.decisions.ProcessedEvent.count_recent_by_sender", return_value=0)
    @patch("apps.core.decisions.UserBlacklist.find_by_sender", return_value=None)
    def test_negative_comment_replies_and_escalates(self, *_):
        self.engine.ai_client.analyze.return_value = DifyAnalysisResult(
            intent="complaint",
            sentiment="negative",
            confidence=0.9,
        )

        decision = self.engine.decide(
            {
                "event_type": "comment",
                "sender_id": "user-1",
                "page_id": "page-1",
                "comment_id": "comment-1",
                "message_text": "bad",
            }
        )

        self.assertEqual(decision.action_type, "reply_comment")
        self.assertTrue(decision.payload["escalate"])
