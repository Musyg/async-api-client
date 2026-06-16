"""Retry policy: exponential backoff with jitter, honoring Retry-After."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

__all__ = ["RetryPolicy"]


@dataclass
class RetryPolicy:
    """
    Computes retry delays and decides which responses are retriable.

    Delay is `base_delay * 2**attempt`, capped at `max_delay`, with optional
    full jitter. A server-provided `Retry-After` (seconds) always wins.
    """

    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 30.0
    jitter: bool = True
    retriable_statuses: FrozenSet[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )

    def is_retriable_status(self, status_code: int) -> bool:
        """True if a response with this status should be retried."""
        return status_code in self.retriable_statuses

    def compute_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """
        Delay before retry `attempt` (0-based). Honors `retry_after` when given,
        otherwise exponential backoff with optional full jitter.
        """
        if retry_after is not None and retry_after >= 0:
            return min(retry_after, self.max_delay)
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            return random.uniform(0, delay)
        return delay

    @staticmethod
    def parse_retry_after(value: Optional[str]) -> Optional[float]:
        """Parse a Retry-After header value expressed in seconds."""
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None  # HTTP-date form not handled; fall back to backoff
