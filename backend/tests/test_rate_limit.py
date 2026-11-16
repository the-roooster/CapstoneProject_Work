from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from app.rate_limit import LoginRateLimiter


def test_five_failures_then_block_and_expire():
    now = [100.0]
    limiter = LoginRateLimiter(clock=lambda: now[0])
    key = ("192.0.2.1", "analyst@example.com")
    called = []
    def fail():
        called.append(True)
        return False

    assert [limiter.attempt(key, fail) for _ in range(5)] == [False] * 5
    assert limiter.attempt(key, fail) is None
    assert len(called) == 5
    now[0] += 60
    assert limiter.attempt(key, fail) is False


def test_isolated_keys_and_success_resets():
    limiter = LoginRateLimiter()
    key = ("192.0.2.1", "a@example.com")
    for _ in range(4):
        assert limiter.attempt(key, lambda: False) is False
    assert limiter.attempt(("192.0.2.2", "a@example.com"), lambda: False) is False
    assert limiter.attempt(("192.0.2.1", "b@example.com"), lambda: False) is False
    assert limiter.attempt(key, lambda: True) is True
    for _ in range(5):
        assert limiter.attempt(key, lambda: False) is False
    assert limiter.attempt(key, lambda: False) is None


def test_concurrent_failures_cannot_bypass_limit():
    limiter = LoginRateLimiter()
    key = ("192.0.2.1", "a@example.com")
    calls = []
    lock = Lock()
    def fail():
        with lock:
            calls.append(1)
        return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: limiter.attempt(key, fail), range(20)))
    assert results.count(False) == 5
    assert results.count(None) == 15
    assert len(calls) == 5
