import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """In-process sliding-window limiter keyed by client IP.

    Good enough for a single instance; a multi-instance deployment should move this to Redis
    or the reverse proxy.
    """

    def __init__(self, limit: int, window_seconds: float = 60):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.limit <= 0:
            return
        current = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and current - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = int(self.window - (current - hits[0])) + 1
                raise HTTPException(
                    429, "Too many requests, please slow down", headers={"Retry-After": str(retry_after)}
                )
            hits.append(current)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request) -> None:
        self.check(request.client.host if request.client else "unknown")
