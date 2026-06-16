"""Tests for AsyncAPIClient using httpx.MockTransport (no network)."""

import asyncio

import httpx

from async_api_client import APIError, AsyncAPIClient, RetryPolicy


def make_client(handler):
    return AsyncAPIClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(handler),
        retry=RetryPolicy(base_delay=0.01, jitter=False, max_retries=3),
    )


def test_429_then_success():
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json={"ok": True})

    async def run():
        async with make_client(handler) as api:
            assert await api.get_json("/x") == {"ok": True}
            assert state["n"] == 2

    asyncio.run(run())


def test_persistent_500_raises():
    def handler(request):
        return httpx.Response(500, json={})

    async def run():
        async with make_client(handler) as api:
            try:
                await api.get_json("/x")
            except APIError as e:
                assert e.status_code == 500
                return
            raise AssertionError("expected APIError")

    asyncio.run(run())


def test_404_not_retried():
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        return httpx.Response(404, json={})

    async def run():
        async with make_client(handler) as api:
            try:
                await api.get_json("/missing")
            except APIError as e:
                assert e.status_code == 404
            assert state["n"] == 1  # no retry on non-retriable status

    asyncio.run(run())


def test_pagination_follows_link_header():
    def handler(request):
        if "page_info" in request.url.params:
            return httpx.Response(200, json={"items": [3, 4]})
        nxt = "https://api.test/list?page_info=abc"
        return httpx.Response(
            200, json={"items": [1, 2]}, headers={"Link": f'<{nxt}>; rel="next"'}
        )

    async def run():
        async with make_client(handler) as api:
            got = [x async for x in api.paginate("/list", items_key="items")]
            assert got == [1, 2, 3, 4]

    asyncio.run(run())
