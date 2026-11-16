"""Process-local login throttling keyed by client IP and normalized email."""
from collections import deque
from threading import Lock
from time import monotonic
from typing import Callable


class LoginRateLimiter:
    def __init__(self, limit=5, window_seconds=60, clock=monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._failures = {}
        self._lock = Lock()

    def attempt(self, key: tuple[str, str], authenticate: Callable[[], bool]) -> bool | None:
        """Return None when blocked; successful authentication clears failures."""
        with self._lock:
            now = self.clock()
            for old_key, entries in list(self._failures.items()):
                while entries and entries[0] <= now - self.window_seconds:
                    entries.popleft()
                if not entries:
                    del self._failures[old_key]
            failures = self._failures.get(key)
            if failures is not None and len(failures) >= self.limit:
                return None
            success = authenticate()
            if success:
                self._failures.pop(key, None)
            else:
                self._failures.setdefault(key, deque()).append(now)
            return success


login_rate_limiter = LoginRateLimiter()
