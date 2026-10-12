from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(UTC)


class FeedbackCategory(StrEnum):
    GENERAL = "general"
    BUG = "bug"
    FEATURE = "feature"
    USABILITY = "usability"


class FeedbackStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RequirementStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"


REQUIREMENT_TRANSITIONS: dict[RequirementStatus, set[RequirementStatus]] = {
    RequirementStatus.DRAFT: {RequirementStatus.DRAFT, RequirementStatus.CONFIRMED},
    RequirementStatus.CONFIRMED: {RequirementStatus.CONFIRMED, RequirementStatus.DELIVERED},
    RequirementStatus.DELIVERED: {RequirementStatus.DELIVERED},
}


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    workspace: Mapped[Workspace] = relationship(lazy="joined")


class Token(Base):
    """Opaque session token. Only a SHA-256 digest is stored, so a database leak does not leak sessions."""

    __tablename__ = "tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


requirement_sources = Table(
    "requirement_sources",
    Base.metadata,
    Column("requirement_id", ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True),
    # One requirement per feedback item keeps draft creation idempotent.
    Column("feedback_id", ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True, unique=True),
)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("workspace_id", "external_key", name="uq_feedback_external"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    external_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), default=FeedbackCategory.GENERAL)
    page_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=FeedbackStatus.NEW, index=True)
    tags: Mapped[str] = mapped_column(String(500), default="")
    assignee: Mapped[str | None] = mapped_column(String(254), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("feedback_id", "version", name="uq_analysis_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=AnalysisStatus.QUEUED)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    problem: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    open_questions: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default=RequirementStatus.DRAFT, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    sources: Mapped[list[Feedback]] = relationship(secondary=requirement_sources, lazy="selectin", order_by=Feedback.id)
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="requirement", lazy="selectin", order_by="Task.id", cascade="all, delete-orphan"
    )

    @property
    def source_feedback_ids(self) -> list[int]:
        return [feedback.id for feedback in self.sources]


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    requirement: Mapped[Requirement] = relationship(back_populates="tasks")
