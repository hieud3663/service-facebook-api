"""Local rule-based spam detector for fast moderation signals before AI."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
REPEATED_CHAR_RE = re.compile(r"(.)\1{5,}", re.IGNORECASE)
SCAM_KEYWORDS = {
    "free money",
    "click here",
    "nhận quà",
    "trúng thưởng",
    "kiếm tiền",
    "vay tiền",
    "đầu tư",
    "crypto",
    "casino",
    "telegram",
    "zalo",
}
SUSPICIOUS_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.me",
    "telegram.me",
}


@dataclass(frozen=True)
class SpamDetectionResult:
    is_spam: bool = False
    is_malicious_link: bool = False
    score: int = 0
    reason: str = ""
    signals: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    message_hash: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_spam": self.is_spam,
            "is_malicious_link": self.is_malicious_link,
            "score": self.score,
            "reason": self.reason,
            "signals": self.signals,
            "links": self.links,
            "message_hash": self.message_hash,
        }


class LocalSpamDetector:
    """Detect obvious spam without waiting for AI."""

    SPAM_SCORE_THRESHOLD = 3

    def detect(self, message_text: str) -> SpamDetectionResult:
        normalized = " ".join((message_text or "").strip().lower().split())
        message_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""
        if not normalized:
            return SpamDetectionResult(message_hash=message_hash)

        signals: list[str] = []
        links = URL_RE.findall(normalized)
        score = 0
        malicious_link = False

        if links:
            signals.append("contains_link")
            score += 1

        for link in links:
            if any(domain in link for domain in SUSPICIOUS_DOMAINS):
                signals.append("suspicious_short_link")
                score += 3
                malicious_link = True
                break

        keyword_hits = [keyword for keyword in SCAM_KEYWORDS if keyword in normalized]
        if keyword_hits:
            signals.append("scam_keyword")
            score += min(len(keyword_hits), 3)

        if REPEATED_CHAR_RE.search(normalized):
            signals.append("repeated_characters")
            score += 1

        words = normalized.split()
        if len(words) >= 8:
            repeated_ratio = 1 - (len(set(words)) / len(words))
            if repeated_ratio >= 0.45:
                signals.append("repeated_words")
                score += 2

        is_spam = score >= self.SPAM_SCORE_THRESHOLD or malicious_link
        reason = ", ".join(signals)

        return SpamDetectionResult(
            is_spam=is_spam,
            is_malicious_link=malicious_link,
            score=score,
            reason=reason,
            signals=signals,
            links=links,
            message_hash=message_hash,
        )
