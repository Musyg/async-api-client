# async-api-client

[![CI](https://github.com/Musyg/async-api-client/actions/workflows/ci.yml/badge.svg)](https://github.com/Musyg/async-api-client/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

A small, resilient async REST client. It wraps `httpx.AsyncClient` with the
three things every real-world API integration ends up needing:

- **Token-bucket rate limiting** - stay under a provider's request budget with
  a configurable rate and burst.
- **Retries with backoff** - exponential backoff plus full jitter, and it
  honors a server's `Retry-After` header on `429`.
- **Link-header pagination** - follows RFC 5988 `rel="next"` (Shopify, GitHub,
  and many others), so you iterate results without hand-rolling cursors.

Subclass `AsyncAPIClient` to build a typed wrapper for any API.

> Extracted and generalized from the commerce-integration layer of
> [Talos](https://github.com/Musyg/talos), my agentic platform, which drives several storefront and
> marketplace APIs concurrently.

## Install

```bash
pip install async-api-client
```

## Usage

```python
from async_api_client import AsyncAPIClient, AsyncTokenBucket, RetryPolicy

async with AsyncAPIClient(
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer ..."},
    rate_limiter=AsyncTokenBucket(rate=2, capacity=4),   # 2 req/s, burst 4
    retry=RetryPolicy(max_retries=4, base_delay=1.0),
) as api:
    order = await api.get_json("/v1/orders/42")
    async for item in api.paginate("/v1/orders", items_key="orders"):
        process(item)
```

On a `429` or `5xx`, the client backs off and retries automatically; a `429`
with `Retry-After` waits exactly that long. Non-retriable errors (`404`, `400`)
raise `APIError` immediately with the status code attached.

## Building a typed client

`examples/shopify_example.py` shows the base specialized into a minimal Shopify
Admin client - rate limiter tuned to Shopify's REST budget, cursor pagination,
typed accessors:

```python
class ShopifyClient(AsyncAPIClient):
    def __init__(self, shop, token, api_version="2025-10"):
        super().__init__(
            base_url=f"https://{shop}/admin/api/{api_version}",
            headers={"X-Shopify-Access-Token": token},
            rate_limiter=AsyncTokenBucket(rate=2, capacity=4),
            retry=RetryPolicy(max_retries=4, base_delay=1.0),
        )

    async def get_products(self, limit=50, status="active"):
        data = await self.get_json("products.json", params={"limit": limit, "status": status})
        return data.get("products", [])
```

## Tests

```bash
pip install "async-api-client[dev]"
pytest
```

The client tests use `httpx.MockTransport`, so they cover the 429-then-success
path, persistent-5xx failure, non-retriable 404, and Link-header pagination
without touching the network.

## License

MIT
