import threading
import time
from collections import OrderedDict, deque

from fastapi import HTTPException, Request

from .config import settings


def client_ip(request: Request) -> str:
    """The caller's IP, trusting X-Forwarded-For only as far as our own reverse proxies.

    Each trusted proxy appends the address it received the request from, so with N proxies the
    client is the Nth entry from the right. Entries further left were written by the client and
    can be forged, so they are never used.
    """
    hops = settings.trusted_proxy_hops
    if hops > 0:
        forwarded = [host.strip() for value in request.headers.getlist("x-forwarded-for") for host in value.split(",")]
        forwarded = [host for host in forwarded if host]
        if len(forwarded) >= hops:
            return forwarded[-hops]
        # Fewer entries than configured proxies: the header was not set by them, so fall back to the peer.
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """In-process sliding-window limiter keyed by client IP.

    Keys are kept in least-recently-used order and dropped once their window has passed, and the
    table is capped at `max_keys`, so a flood of distinct IPs cannot grow memory without bound.

    Good enough for a single instance; a multi-instance deployment should move this to Redis
    or the reverse proxy.
    """

    def __init__(self, limit: int, window_seconds: float = 60, max_keys: int = 10_000):
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.limit <= 0:
            return
        current = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()
            else:
                self._hits.move_to_end(key)
            while hits and current - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = int(self.window - (current - hits[0])) + 1
                raise HTTPException(
                    429, "Too many requests, please slow down", headers={"Retry-After": str(retry_after)}
                )
            hits.append(current)
            self._evict(current)

    def _evict(self, current: float) -> None:
        # Oldest-used keys come first; stop at the first one that is still inside its window.
        while self._hits:
            hits = next(iter(self._hits.values()))
            if len(self._hits) > self.max_keys or not hits or current - hits[-1] > self.window:
                self._hits.popitem(last=False)
            else:
                break

    def __len__(self) -> int:
        return len(self._hits)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request) -> None:
        self.check(client_ip(request))
