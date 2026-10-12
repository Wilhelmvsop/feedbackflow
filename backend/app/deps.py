from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, get_db
from .models import Token, User
from .ratelimit import RateLimiter
from .security import hash_token
from .services import SessionFactory

DB = Annotated[Session, Depends(get_db)]

login_limiter = RateLimiter(settings.login_rate_limit)
public_feedback_limiter = RateLimiter(settings.public_feedback_rate_limit)


def get_session_factory() -> SessionFactory:
    """Session factory for background work that outlives the request (overridable in tests)."""
    return SessionLocal


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    return authorization.removeprefix("Bearer ").strip()


def current_session(db: DB, token: Annotated[str, Depends(bearer_token)]) -> Token:
    session = db.scalar(select(Token).where(Token.token_hash == hash_token(token)))
    if not session or _aware(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(
            401, "Your session has expired, please sign in again", headers={"WWW-Authenticate": "Bearer"}
        )
    return session


def current_user(db: DB, session: Annotated[Token, Depends(current_session)]) -> User:
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Invalid session", headers={"WWW-Authenticate": "Bearer"})
    return user


def _aware(value: datetime) -> datetime:
    # SQLite drops tzinfo on round-trip; values are always written in UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


CurrentUser = Annotated[User, Depends(current_user)]
CurrentSession = Annotated[Token, Depends(current_session)]
Sessions = Annotated[SessionFactory, Depends(get_session_factory)]
