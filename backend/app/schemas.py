from datetime import UTC, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from .models import AnalysisStatus, FeedbackCategory, FeedbackStatus, RequirementStatus

T = TypeVar("T")

# SQLite drops tzinfo on round-trip; all stored timestamps are UTC, so always emit them with an offset.
UTCDateTime = Annotated[datetime, AfterValidator(lambda v: v if v.tzinfo else v.replace(tzinfo=UTC))]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -------------------------------------------------------------------


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class WorkspaceOut(ORMModel):
    id: int
    slug: str
    name: str


class UserOut(BaseModel):
    email: str
    workspace: WorkspaceOut


class LoginOut(UserOut):
    token: str
    expires_at: UTCDateTime


# --- Feedback ---------------------------------------------------------------


class FeedbackIn(BaseModel):
    message: str = Field(min_length=3, max_length=5000)
    category: FeedbackCategory = FeedbackCategory.GENERAL
    page_path: str | None = Field(default=None, max_length=500)
    external_key: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Message must contain at least 3 characters")
        return value


class FeedbackSubmitted(BaseModel):
    id: int
    status: FeedbackStatus
    duplicate: bool


class FeedbackUpdate(BaseModel):
    status: FeedbackStatus | None = None
    tags: str | None = Field(default=None, max_length=500)
    assignee: str | None = Field(default=None, max_length=254)


class FeedbackBulkUpdate(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    status: FeedbackStatus


class BulkResult(BaseModel):
    updated: int


class RelatedFeedback(BaseModel):
    id: int
    reason: str
    message: str


class AnalysisResult(BaseModel):
    problem: str
    suggested_title: str
    known_facts: list[str]
    assumptions: list[str]
    open_questions: list[str]
    acceptance_criteria: list[str]
    boundaries: list[str] = []
    related_feedback_ids: list[int] = []
    related_feedback: list[RelatedFeedback] = []


class AnalysisOut(BaseModel):
    id: int
    status: AnalysisStatus
    version: int
    result: AnalysisResult | None
    error: str | None


class AnalysisJob(BaseModel):
    analysis_id: int
    status: AnalysisStatus
    version: int


class FeedbackOut(ORMModel):
    id: int
    message: str
    category: FeedbackCategory
    page_path: str | None
    status: FeedbackStatus
    tags: str
    assignee: str | None
    created_at: UTCDateTime
    requirement_id: int | None = None
    analysis: AnalysisOut | None = None


class FeedbackStats(BaseModel):
    total: int
    new: int
    triaged: int
    in_progress: int
    resolved: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# --- Requirements -----------------------------------------------------------


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be blank")
        return value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


class TaskOut(ORMModel):
    id: int
    title: str
    done: bool


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    problem: str | None = Field(default=None, max_length=10_000)
    acceptance_criteria: str | None = Field(default=None, max_length=10_000)
    open_questions: str | None = Field(default=None, max_length=10_000)
    status: RequirementStatus | None = None


class RequirementOut(ORMModel):
    id: int
    title: str
    problem: str
    acceptance_criteria: str
    open_questions: str
    status: RequirementStatus
    source_feedback_ids: list[int]
    tasks: list[TaskOut]
    created_at: UTCDateTime
    updated_at: UTCDateTime
