"""Small in-memory circuit breaker for downstream calls."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when a circuit is open and the downstream call is blocked."""


@dataclass
class CircuitSnapshot:
    name: str
    state: str
    failure_count: int
    opened_at: float | None


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, name: str, failure_threshold: int, reset_timeout_seconds: int):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.reset_timeout_seconds = max(1, reset_timeout_seconds)
        self.state = self.CLOSED
        self.failure_count = 0
        self.opened_at: float | None = None
        self._lock = threading.Lock()

    def call(self, func: Callable[[], T]) -> T:
        self._before_call()
        try:
            result = func()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    def _before_call(self) -> None:
        with self._lock:
            if self.state != self.OPEN:
                return

            elapsed = time.monotonic() - (self.opened_at or 0)
            if elapsed >= self.reset_timeout_seconds:
                self.state = self.HALF_OPEN
                logger.warning("Circuit %s moved to half_open", self.name)
                return

            raise CircuitOpenError(f"circuit {self.name} is open")

    def record_success(self) -> None:
        with self._lock:
            if self.state != self.CLOSED:
                logger.info("Circuit %s closed after successful probe", self.name)
            self.state = self.CLOSED
            self.failure_count = 0
            self.opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                self.opened_at = time.monotonic()
                logger.error("Circuit %s opened after %d failures", self.name, self.failure_count)

    def snapshot(self) -> CircuitSnapshot:
        with self._lock:
            return CircuitSnapshot(
                name=self.name,
                state=self.state,
                failure_count=self.failure_count,
                opened_at=self.opened_at,
            )

    def reset(self) -> None:
        with self._lock:
            self.state = self.CLOSED
            self.failure_count = 0
            self.opened_at = None

