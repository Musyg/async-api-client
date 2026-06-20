"""
Example: a minimal Shopify Admin client built on AsyncAPIClient.

Shows how the resilient base specializes into a real API wrapper - rate
limiting tuned to Shopify's 2 req/s REST budget, cursor pagination via the
Link header, typed accessors. This is illustrative, not a full SDK.

    client = ShopifyClient(shop="my-shop.myshopify.com", token="shpat_...")
    async with client:
        products = await client.get_products(limit=50)
        async for order in client.iter_orders(status="any"):
            ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from async_api_client import AsyncAPIClient, AsyncTokenBucket, RetryPolicy

SHOPIFY_API_VERSION = "2025-10"


class ShopifyClient(AsyncAPIClient):
    def __init__(self, shop: str, token: str, api_version: str = SHOPIFY_API_VERSION):
        super().__init__(
            base_url=f"https://{shop}/admin/api/{api_version}",
            headers={
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            # Shopify REST allows ~2 requests/second with a small burst bucket.
            rate_limiter=AsyncTokenBucket(rate=2, capacity=4),
            retry=RetryPolicy(max_retries=4, base_delay=1.0),
        )

    async def get_products(self, limit: int = 50, status: str = "active") -> list[dict[str, Any]]:
        data = await self.get_json("products.json", params={"limit": min(limit, 250), "status": status})
        return data.get("products", [])

    async def iter_orders(self, status: str = "any") -> AsyncGenerator[dict[str, Any], None]:
        async for order in self.paginate(
            "orders.json", items_key="orders", params={"status": status, "limit": 250}
        ):
            yield order

    async def create_product(self, product: dict[str, Any]) -> dict[str, Any]:
        data = await self.post_json("products.json", json={"product": product})
        return data.get("product", {})
