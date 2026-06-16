"""Tests for the retry policy."""

from async_api_client import RetryPolicy


def test_retry_after_wins_and_caps():
    p = RetryPolicy(base_delay=1, max_delay=30, jitter=False)
    assert p.compute_delay(0, retry_after=5) == 5
    assert p.compute_delay(3, retry_after=100) == 30  # capped at max_delay


def test_exponential_backoff_without_jitter():
    p = RetryPolicy(base_delay=1, max_delay=30, jitter=False)
    assert p.compute_delay(0) == 1
    assert p.compute_delay(1) == 2
    assert p.compute_delay(2) == 4


def test_jitter_is_bounded():
    p = RetryPolicy(base_delay=1, max_delay=30, jitter=True)
    for _ in range(200):
        assert 0 <= p.compute_delay(3) <= 8  # base 2**3 = 8


def test_retriable_statuses():
    p = RetryPolicy()
    assert p.is_retriable_status(429)
    assert p.is_retriable_status(503)
    assert not p.is_retriable_status(404)
    assert not p.is_retriable_status(200)


def test_parse_retry_after():
    p = RetryPolicy()
    assert p.parse_retry_after("5") == 5.0
    assert p.parse_retry_after(None) is None
    assert p.parse_retry_after("Wed, 21 Oct 2099 07:28:00 GMT") is None  # HTTP-date not handled
