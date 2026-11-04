"""Backoff and retry-budget helpers for gateway calls."""
import random
import threading


def backoff_delay(attempt, base_s, cap_s, rng=random.random):
    """Full-jitter exponential backoff: a random delay in [0, min(cap, base * 2**attempt))."""
    return rng() * min(cap_s, base_s * (2 ** attempt))


class RetryBudget:
    """Caps retries at a fraction of first attempts across the process.

    Every new payment deposits `ratio` tokens and every retry after a timeout
    spends one. When the gateway is slow for everyone, retries stop instead of
    multiplying the load on it.
    """

    def __init__(self, ratio, min_tokens=10.0, max_tokens=100.0):
        self._ratio = ratio
        self._tokens = min_tokens
        self._max = max_tokens
        self._lock = threading.Lock()

    def record_attempt(self):
        with self._lock:
            self._tokens = min(self._max, self._tokens + self._ratio)

    def try_spend(self):
        with self._lock:
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False
