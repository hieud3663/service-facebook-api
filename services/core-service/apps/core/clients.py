"""HTTP client for Dify AI."""
import json
import logging
from typing import Any

import requests
from django.conf import settings

from .circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

VALID_INTENTS = {
    "price_question",
    "complaint",
    "support",
    "praise",
    "general_interaction",
    "spam",
    "unknown",
}
VALID_SENTIMENTS = {"positive", "neutral", "negative"}


class DifyAnalysisResult:
    """Parsed result from Dify AI."""

    def __init__(
        self,
        intent: str = "unknown",
        sentiment: str = "neutral",
        is_spam: bool = False,
        is_malicious_link: bool = False,
        confidence: float = 0.0,
        reason: str = "",
        reply_content: str = "",
        raw_response: dict | None = None,
        parse_error: str = "",
    ):
        self.intent = intent if intent in VALID_INTENTS else "unknown"
        self.sentiment = sentiment if sentiment in VALID_SENTIMENTS else "neutral"
        self.is_spam = is_spam
        self.is_malicious_link = is_malicious_link
        self.confidence = max(0.0, min(float(confidence or 0.0), 1.0))
        self.reason = reason
        self.reply_content = reply_content
        self.raw_response = raw_response or {}
        self.parse_error = parse_error

    @classmethod
    def from_dify_response(cls, raw: dict) -> "DifyAnalysisResult":
        """Parse the JSON output from Dify workflow/completion."""
        answer_text: Any = ""

        if "data" in raw and "outputs" in raw.get("data", {}):
            outputs = raw["data"]["outputs"]
            answer_text = outputs.get("output", "") or outputs.get("text", "") or outputs.get("result", "") or outputs
        elif "answer" in raw:
            answer_text = raw["answer"]
        else:
            answer_text = raw

        try:
            parsed = json.loads(answer_text) if isinstance(answer_text, str) else answer_text
            if not isinstance(parsed, dict):
                raise ValueError("Dify answer is not a JSON object")
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Dify returned invalid structured answer: %s", str(answer_text)[:200])
            return cls(raw_response=raw, parse_error=str(exc))

        try:
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

        return cls(
            intent=str(parsed.get("intent", "unknown") or "unknown"),
            sentiment=str(parsed.get("sentiment", "neutral") or "neutral"),
            is_spam=bool(parsed.get("is_spam", False)),
            is_malicious_link=bool(parsed.get("is_malicious_link", False)),
            confidence=max(0.0, min(confidence, 1.0)),
            reason=str(parsed.get("reason", "") or ""),
            reply_content=str(parsed.get("reply_content", "") or ""),
            raw_response=raw,
        )


class DifyAIClient:
    """Calls Dify.AI API to classify intent and sentiment."""

    def __init__(self):
        self.api_url = settings.DIFY_API_URL.rstrip("/")
        self.api_key = settings.DIFY_API_KEY
        self.timeout = 30
        self.breaker = CircuitBreaker(
            "dify-ai",
            settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
        )

    def analyze(self, message_text: str) -> DifyAnalysisResult:
        """Send text to Dify and return structured analysis."""
        if not self.api_key or self.api_key == "your-dify-api-key-here":
            logger.warning("DIFY_API_KEY not configured, returning empty analysis")
            return DifyAnalysisResult()

        if not message_text or not message_text.strip():
            return DifyAnalysisResult()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": {"message_text": message_text},
            "response_mode": "blocking",
            "user": "core-service",
        }

        try:
            def request_call():
                response = requests.post(
                    f"{self.api_url}/workflows/run",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response

            resp = self.breaker.call(request_call)
            return DifyAnalysisResult.from_dify_response(resp.json())
        except CircuitOpenError as exc:
            logger.error("Dify circuit is open: %s", exc)
            return DifyAnalysisResult(reason="dify circuit open", parse_error=str(exc))
        except requests.Timeout:
            logger.error("Dify AI timeout for text: %s", message_text[:100])
            return DifyAnalysisResult()
        except requests.RequestException as exc:
            logger.error("Dify AI request failed: %s", exc)
            return DifyAnalysisResult()
