from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response
from sqlalchemy import func, or_, select, update

from .. import services
from ..deps import DB, CurrentUser, Sessions
from ..models import Feedback, FeedbackCategory, FeedbackStatus, now
from ..schemas import (
    AnalysisJob,
    BulkResult,
    FeedbackBulkUpdate,
    FeedbackOut,
    FeedbackStats,
    FeedbackUpdate,
    Page,
    RequirementOut,
)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=Page[FeedbackOut])
def list_feedback(
    db: DB,
    user: CurrentUser,
    q: Annotated[str, Query(max_length=200)] = "",
    status: FeedbackStatus | None = None,
    category: FeedbackCategory | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    stmt = select(Feedback).where(Feedback.workspace_id == user.workspace_id)
    if q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        stmt = stmt.where(or_(Feedback.message.ilike(pattern, escape="\\"), Feedback.tags.ilike(pattern, escape="\\")))
    if status:
        stmt = stmt.where(Feedback.status == status)
    if category:
        stmt = stmt.where(Feedback.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Feedback.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=services.feedback_out(db, list(items)), total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=FeedbackStats)
def feedback_stats(db: DB, user: CurrentUser):
    return services.feedback_stats(db, user.workspace_id)


@router.post("/bulk", response_model=BulkResult)
def bulk_update_status(data: FeedbackBulkUpdate, db: DB, user: CurrentUser):
    """Set one status on several items. IDs outside the caller's workspace are silently skipped."""
    result = db.execute(
        update(Feedback)
        .where(Feedback.workspace_id == user.workspace_id, Feedback.id.in_(data.ids))
        .values(status=data.status, updated_at=now())
    )
    db.commit()
    return BulkResult(updated=result.rowcount)


@router.get("/{feedback_id}", response_model=FeedbackOut)
def get_feedback(feedback_id: int, db: DB, user: CurrentUser):
    return services.feedback_out(db, [services.owned_feedback(db, user.workspace_id, feedback_id)])[0]


@router.patch("/{feedback_id}", response_model=FeedbackOut)
def update_feedback(feedback_id: int, data: FeedbackUpdate, db: DB, user: CurrentUser):
    item = services.owned_feedback(db, user.workspace_id, feedback_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    return services.feedback_out(db, [item])[0]


def _job(analysis) -> AnalysisJob:
    return AnalysisJob(analysis_id=analysis.id, status=analysis.status, version=analysis.version)


@router.post("/{feedback_id}/analysis", status_code=202, response_model=AnalysisJob)
def start_analysis(feedback_id: int, background: BackgroundTasks, db: DB, user: CurrentUser, sessions: Sessions):
    item = services.owned_feedback(db, user.workspace_id, feedback_id)
    analysis, created = services.enqueue_analysis(db, item)
    if created:
        background.add_task(services.run_analysis, analysis.id, sessions)
    return _job(analysis)


@router.post("/{feedback_id}/analysis/retry", status_code=202, response_model=AnalysisJob)
def retry_analysis(feedback_id: int, background: BackgroundTasks, db: DB, user: CurrentUser, sessions: Sessions):
    item = services.owned_feedback(db, user.workspace_id, feedback_id)
    analysis, created = services.enqueue_analysis(db, item, retry=True)
    if created:
        background.add_task(services.run_analysis, analysis.id, sessions)
    return _job(analysis)


@router.post("/{feedback_id}/requirement", status_code=201, response_model=RequirementOut)
def create_requirement(feedback_id: int, response: Response, db: DB, user: CurrentUser):
    item = services.owned_feedback(db, user.workspace_id, feedback_id)
    requirement, created = services.create_requirement_from_analysis(db, item)
    if not created:
        response.status_code = 200
    return requirement
