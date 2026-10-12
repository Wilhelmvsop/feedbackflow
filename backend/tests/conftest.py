import os

# Configure before the app is imported: no file database, no external model, no demo seeding.
os.environ.update({"APP_ENV": "test", "DATABASE_URL": "sqlite://", "AI_API_KEY": "", "SEED_DEMO": "false"})

from datetime import UTC, datetime, timedelta  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.deps import get_session_factory, login_limiter, public_feedback_limiter  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Feedback, Requirement, Token, User, Workspace, requirement_sources  # noqa: E402
from app.security import hash_password, hash_token  # noqa: E402


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def seeded(db):
    """Two isolated workspaces; tests act as alpha and must never see beta's data."""
    alpha = Workspace(slug="alpha", name="Alpha")
    beta = Workspace(slug="beta", name="Beta")
    db.add_all([alpha, beta])
    db.flush()
    user = User(workspace_id=alpha.id, email="alpha@example.com", password_hash=hash_password("pw"))
    foreign_user = User(workspace_id=beta.id, email="beta@example.com", password_hash=hash_password("pw"))
    db.add_all([user, foreign_user])
    db.flush()
    db.add(
        Token(user_id=user.id, token_hash=hash_token("alpha-token"), expires_at=datetime.now(UTC) + timedelta(days=1))
    )
    first = Feedback(
        workspace_id=alpha.id, message="Uploading files is slow and the progress is unclear.", category="bug"
    )
    foreign = Feedback(workspace_id=beta.id, message="Private feedback from another workspace", category="general")
    db.add_all([first, foreign])
    db.flush()
    foreign_req = Requirement(workspace_id=beta.id, title="Private", problem="Private")
    db.add(foreign_req)
    db.flush()
    db.execute(requirement_sources.insert().values(requirement_id=foreign_req.id, feedback_id=foreign.id))
    db.commit()
    return SimpleNamespace(
        alpha=alpha, beta=beta, user=user, feedback_id=first.id, foreign_id=foreign.id, foreign_req_id=foreign_req.id
    )


@pytest.fixture
def client(session_factory, seeded):
    def override_db():
        with session_factory() as session:
            yield session

    app = create_app(run_startup=False)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    login_limiter.reset()
    public_feedback_limiter.reset()
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": "Bearer alpha-token"})
        test_client.ids = seeded
        yield test_client
