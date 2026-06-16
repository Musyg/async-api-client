"""
async-api-client - a small resilient async REST client: token-bucket rate
limiting, retries with exponential backoff honoring Retry-After, and
Link-header pagination. Subclass `AsyncAPIClient` to build a typed wrapper.
"""

from .client import APIError, AsyncAPIClient
from .rate_limit import AsyncTokenBucket
from .retry import RetryPolicy

__version__ = "0.1.0"

__all__ = ["AsyncAPIClient", "APIError", "AsyncTokenBucket", "RetryPolicy"]
