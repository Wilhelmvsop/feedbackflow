from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select

from ..config import settings
from ..deps import DB, CurrentSession, CurrentUser, login_limiter
from ..models import Token, User
from ..schemas import LoginIn, LoginOut, UserOut, WorkspaceOut
from ..security import hash_token, new_session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut, dependencies=[Depends(login_limiter)])
def login(data: LoginIn, db: DB):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    issued_at = datetime.now(UTC)
    db.execute(delete(Token).where(Token.user_id == user.id, Token.expires_at <= issued_at))
    token = new_session_token()
    expires_at = issued_at + timedelta(hours=settings.token_ttl_hours)
    db.add(Token(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    db.commit()
    return LoginOut(
        token=token, expires_at=expires_at, email=user.email, workspace=WorkspaceOut.model_validate(user.workspace)
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return UserOut(email=user.email, workspace=WorkspaceOut.model_validate(user.workspace))


@router.post("/logout", status_code=204)
def logout(session: CurrentSession, db: DB):
    db.delete(session)
    db.commit()
