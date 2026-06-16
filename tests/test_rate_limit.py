"""Tests for the async token-bucket rate limiter."""

import asyncio
import time

from async_api_client import AsyncTokenBucket


def test_consumes_tokens():
    async def run():
        b = AsyncTokenBucket(rate=100, capacity=2)
        await b.acquire()
        await b.acquire()
        assert b.available < 1.5

    asyncio.run(run())


def test_acquire_above_capacity_raises():
    async def run():
        b = AsyncTokenBucket(rate=10, capacity=2)
        try:
            await b.acquire(3)
        except ValueError:
            return
        raise AssertionError("expected ValueError")

    asyncio.run(run())


def test_throttles_after_burst():
    async def run():
        b = AsyncTokenBucket(rate=10, capacity=1)  # ~0.1s between tokens
        await b.acquire()
        t0 = time.monotonic()
        await b.acquire()
        assert time.monotonic() - t0 >= 0.08

    asyncio.run(run())


def test_invalid_rate_raises():
    try:
        AsyncTokenBucket(rate=0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
