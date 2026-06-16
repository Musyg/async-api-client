"""Async token-bucket rate limiter."""

from __future__ import annotations

import asyncio
import time

__all__ = ["AsyncTokenBucket"]


class AsyncTokenBucket:
    """
    Token bucket for smoothing async request rates.

    `rate` tokens are added per second up to `capacity` (the burst size).
    `acquire()` waits until enough tokens are available, then consumes them.

        bucket = AsyncTokenBucket(rate=2, capacity=4)  # 2 req/s, burst 4
        await bucket.acquire()
    """

    def __init__(self, rate: float, capacity: float | None = None):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._updated = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until `tokens` are available, then consume them."""
        if tokens > self.capacity:
            raise ValueError("requested tokens exceed bucket capacity")
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait = deficit / self.rate
            await asyncio.sleep(wait)

    @property
    def available(self) -> float:
        """Approximate tokens available right now (without consuming)."""
        self._refill()
        return self._tokens
