"""
AsyncAPIClient - a resilient async REST client.

Wraps httpx.AsyncClient with:
- a token-bucket rate limiter,
- retries with exponential backoff + jitter, honoring `Retry-After` on 429,
- Link-header pagination (RFC 5988 `rel="next"`),
- an async context manager for clean connection handling.

    async with AsyncAPIClient(
        base_url="https://api.example.com",
        headers={"Authorization": "Bearer ..."},
        rate_limiter=AsyncTokenBucket(rate=2, capacity=4),
    ) as api:
        data = await api.get_json("/v1/orders", params={"limit": 50})
        async for item in api.paginate("/v1/orders", items_key="orders"):
            ...
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from .rate_limit import AsyncTokenBucket
from .retry import RetryPolicy

logger = logging.getLogger(__name__)

__all__ = ["AsyncAPIClient", "APIError"]


class APIError(Exception):
    """Raised when a request ultimately fails after retries."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class AsyncAPIClient:
    """Resilient async REST client. Subclass it to build a typed API wrapper."""

    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        rate_limiter: Optional[AsyncTokenBucket] = None,
        retry: Optional[RetryPolicy] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.rate_limiter = rate_limiter
        self.retry = retry or RetryPolicy()
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AsyncAPIClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _ensure_client(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
                transport=self._transport,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """
        Perform a request with rate limiting and retry. Retries on connection
        errors and on retriable status codes (429, 5xx), honoring Retry-After.
        Raises APIError if all attempts fail.
        """
        await self._ensure_client()
        assert self._client is not None
        last_exc: Optional[Exception] = None

        for attempt in range(self.retry.max_retries + 1):
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            try:
                response = await self._client.request(method, path, **kwargs)
            except httpx.TransportError as e:
                last_exc = e
                if attempt < self.retry.max_retries:
                    delay = self.retry.compute_delay(attempt)
                    logger.warning("transport error (attempt %d): %s - retry in %.2fs", attempt + 1, e, delay)
                    await _sleep(delay)
                    continue
                raise APIError(f"transport error after {attempt + 1} attempts: {e}") from e

            if self.retry.is_retriable_status(response.status_code) and attempt < self.retry.max_retries:
                retry_after = self.retry.parse_retry_after(response.headers.get("Retry-After"))
                delay = self.retry.compute_delay(attempt, retry_after)
                logger.warning(
                    "status %d (attempt %d) - retry in %.2fs", response.status_code, attempt + 1, delay
                )
                await _sleep(delay)
                continue

            if response.status_code >= 400:
                raise APIError(f"HTTP {response.status_code} for {method} {path}", response.status_code)
            return response

        raise APIError(f"request failed after retries: {last_exc}")

    async def get_json(self, path: str, params: Optional[Dict] = None) -> Any:
        r = await self.request("GET", path, params=params)
        return r.json() if r.text else {}

    async def post_json(self, path: str, json: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        r = await self.request("POST", path, json=json, params=params)
        return r.json() if r.text else {}

    async def put_json(self, path: str, json: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        r = await self.request("PUT", path, json=json, params=params)
        return r.json() if r.text else {}

    async def delete(self, path: str, params: Optional[Dict] = None) -> bool:
        r = await self.request("DELETE", path, params=params)
        return r.status_code < 400

    async def paginate(
        self,
        path: str,
        items_key: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> AsyncGenerator[Any, None]:
        """
        Iterate a paginated endpoint following RFC 5988 `Link: rel="next"`
        headers (used by Shopify, GitHub, and others). If `items_key` is given,
        yields elements of that key; otherwise yields whole pages.
        """
        await self._ensure_client()
        assert self._client is not None
        next_url: Optional[str] = path
        page_params = dict(params or {})

        while next_url:
            if page_params:
                response = await self.request("GET", next_url, params=page_params)
            else:
                response = await self.request("GET", next_url)
            payload = response.json() if response.text else {}
            if items_key is not None:
                for item in payload.get(items_key, []):
                    yield item
            else:
                yield payload

            next_link = response.links.get("next", {}).get("url")
            if not next_link:
                break
            # Follow the absolute next link as-is; its cursor lives in the query.
            next_url = next_link
            page_params = {}


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
