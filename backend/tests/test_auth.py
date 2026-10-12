from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.deps import login_limiter
from app.models import Token
from app.security import hash_token


def test_login_me_and_logout_round_trip(client, db):
    client.headers.pop("Authorization")
    assert client.get("/api/feedback").status_code == 401
    assert client.post("/api/auth/login", json={"email": "alpha@example.com", "password": "wrong"}).status_code == 401

    result = client.post("/api/auth/login", json={"email": " Alpha@Example.com ", "password": "pw"})
    assert result.status_code == 200
    body = result.json()
    assert body["workspace"] == {"id": client.ids.alpha.id, "slug": "alpha", "name": "Alpha"}

    client.headers["Authorization"] = f"Bearer {body['token']}"
    assert client.get("/api/auth/me").json()["email"] == "alpha@example.com"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/feedback").status_code == 401


def test_session_tokens_are_stored_hashed(client, db):
    token = client.post("/api/auth/login", json={"email": "alpha@example.com", "password": "pw"}).json()["token"]
    stored = db.scalars(select(Token.token_hash)).all()
    assert token not in stored
    assert hash_token(token) in stored


def test_expired_session_is_rejected(client, db):
    session = db.scalar(select(Token).where(Token.token_hash == hash_token("alpha-token")))
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(login_limiter, "limit", 3)
    for _ in range(3):
        assert client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
