import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import ratelimit
from app.config import settings
from app.deps import login_limiter
from app.ratelimit import RateLimiter, client_ip

BAD_LOGIN = {"email": "x@example.com", "password": "nope"}


def make_request(*forwarded: str, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(ratelimit.time, "monotonic", clock)
    return clock


# --- Client IP ------------------------------------------------------------------


def test_forwarded_header_is_ignored_without_trusted_proxies(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert client_ip(make_request("203.0.113.9")) == "10.0.0.1"


def test_client_is_taken_from_the_right_of_the_forwarded_chain(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    # The client sent a forged "1.2.3.4"; our proxy appended the address it actually saw.
    assert client_ip(make_request("1.2.3.4, 198.51.100.7")) == "198.51.100.7"

    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(make_request("1.2.3.4, 198.51.100.7, 172.16.0.5")) == "198.51.100.7"


def test_repeated_forwarded_headers_are_read_as_one_list(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(make_request("1.2.3.4", "198.51.100.7")) == "198.51.100.7"


def test_short_forwarded_chain_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(make_request("198.51.100.7")) == "10.0.0.1"
    assert client_ip(make_request()) == "10.0.0.1"


def test_forged_forwarded_for_cannot_dodge_the_login_limit(client, monkeypatch):
    monkeypatch.setattr(login_limiter, "limit", 3)
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    for i in range(3):
        forged = {"X-Forwarded-For": f"10.9.9.{i}, 198.51.100.7"}
        assert client.post("/api/auth/login", json=BAD_LOGIN, headers=forged).status_code == 401
    blocked = client.post("/api/auth/login", json=BAD_LOGIN, headers={"X-Forwarded-For": "10.9.9.99, 198.51.100.7"})
    assert blocked.status_code == 429


def test_forwarded_for_is_not_trusted_when_exposed_directly(client, monkeypatch):
    monkeypatch.setattr(login_limiter, "limit", 3)
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    for i in range(3):
        client.post("/api/auth/login", json=BAD_LOGIN, headers={"X-Forwarded-For": f"10.9.9.{i}"})
    blocked = client.post("/api/auth/login", json=BAD_LOGIN, headers={"X-Forwarded-For": "10.9.9.99"})
    assert blocked.status_code == 429


# --- Memory bounds ---------------------------------------------------------------


def test_keys_are_dropped_once_their_window_has_passed(clock):
    limiter = RateLimiter(limit=5, window_seconds=60)
    for i in range(100):
        limiter.check(f"198.51.100.{i}")
    assert len(limiter) == 100

    clock.now += 61
    limiter.check("203.0.113.1")
    assert len(limiter) == 1


def test_recently_used_keys_survive_eviction(clock):
    limiter = RateLimiter(limit=5, window_seconds=60)
    limiter.check("old")
    clock.now += 30
    limiter.check("recent")
    clock.now += 31  # "old" is past its window, "recent" is not
    limiter.check("new")
    assert len(limiter) == 2


def test_key_table_is_capped(clock):
    limiter = RateLimiter(limit=5, window_seconds=60, max_keys=50)
    for i in range(1000):
        limiter.check(f"2001:db8::{i:x}")
    assert len(limiter) == 50


def test_active_key_stays_limited_while_others_are_evicted(clock):
    limiter = RateLimiter(limit=2, window_seconds=60, max_keys=10)
    limiter.check("attacker")
    limiter.check("attacker")
    for i in range(100):
        limiter.check(f"198.51.100.{i}")
        if i % 5 == 0:
            # Even a rejected request counts as use, so the key is not evicted and its count not reset.
            with pytest.raises(HTTPException) as exc:
                limiter.check("attacker")
            assert exc.value.status_code == 429
    assert len(limiter) == 10
