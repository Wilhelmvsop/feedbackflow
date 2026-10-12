"""Workspace-scoped business logic shared by the HTTP API and the MCP server."""

import json
import logging
from collections.abc import Callable, Iterable

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .analysis import analyze
from .models import (
    REQUIREMENT_TRANSITIONS,
    Analysis,
    AnalysisStatus,
    Feedback,
    FeedbackStatus,
    Requirement,
    RequirementStatus,
    Workspace,
    now,
    requirement_sources,
)
from .schemas import AnalysisOut, AnalysisResult, FeedbackIn, FeedbackOut, FeedbackStats

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


class NotFound(LookupError):
    pass


class Conflict(RuntimeError):
    pass


# --- Lookups ------------------------------------------------------------------


def workspace_by_slug(db: Session, slug: str) -> Workspace:
    workspace = db.scalar(select(Workspace).where(Workspace.slug == slug))
    if not workspace:
        raise NotFound("Workspace not found")
    return workspace


def owned_feedback(db: Session, workspace_id: int, feedback_id: int) -> Feedback:
    item = db.scalar(select(Feedback).where(Feedback.id == feedback_id, Feedback.workspace_id == workspace_id))
    if not item:
        raise NotFound("Feedback not found")
    return item


def owned_requirement(db: Session, workspace_id: int, requirement_id: int) -> Requirement:
    item = db.scalar(
        select(Requirement).where(Requirement.id == requirement_id, Requirement.workspace_id == workspace_id)
    )
    if not item:
        raise NotFound("Requirement not found")
    return item


def latest_analysis(db: Session, feedback_id: int) -> Analysis | None:
    return db.scalar(select(Analysis).where(Analysis.feedback_id == feedback_id).order_by(Analysis.version.desc()))


def latest_analyses(db: Session, feedback_ids: Iterable[int]) -> dict[int, Analysis]:
    """Latest analysis per feedback item in a single query (avoids N+1 on list pages)."""
    ids = list(feedback_ids)
    if not ids:
        return {}
    newest = (
        select(Analysis.feedback_id, func.max(Analysis.version).label("version"))
        .where(Analysis.feedback_id.in_(ids))
        .group_by(Analysis.feedback_id)
        .subquery()
    )
    rows = db.scalars(
        select(Analysis).join(
            newest, (Analysis.feedback_id == newest.c.feedback_id) & (Analysis.version == newest.c.version)
        )
    )
    return {row.feedback_id: row for row in rows}


def requirement_ids(db: Session, feedback_ids: Iterable[int]) -> dict[int, int]:
    ids = list(feedback_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(requirement_sources.c.feedback_id, requirement_sources.c.requirement_id).where(
            requirement_sources.c.feedback_id.in_(ids)
        )
    )
    return {feedback_id: requirement_id for feedback_id, requirement_id in rows}


# --- Serialization --------------------------------------------------------------


def analysis_out(analysis: Analysis | None) -> AnalysisOut | None:
    if not analysis:
        return None
    result = AnalysisResult.model_validate_json(analysis.result_json) if analysis.result_json else None
    return AnalysisOut(
        id=analysis.id, status=analysis.status, version=analysis.version, result=result, error=analysis.error
    )


def feedback_out(db: Session, items: list[Feedback]) -> list[FeedbackOut]:
    ids = [item.id for item in items]
    analyses = latest_analyses(db, ids)
    linked = requirement_ids(db, ids)
    return [
        FeedbackOut.model_validate(item).model_copy(
            update={"analysis": analysis_out(analyses.get(item.id)), "requirement_id": linked.get(item.id)}
        )
        for item in items
    ]


# --- Feedback -------------------------------------------------------------------


def submit_feedback(db: Session, workspace: Workspace, data: FeedbackIn) -> tuple[Feedback, bool]:
    """Store widget feedback. A repeated external_key returns the original row instead of a duplicate."""

    def existing() -> Feedback | None:
        if not data.external_key:
            return None
        return db.scalar(
            select(Feedback).where(Feedback.workspace_id == workspace.id, Feedback.external_key == data.external_key)
        )

    if found := existing():
        return found, True
    item = Feedback(
        workspace_id=workspace.id,
        message=data.message,
        category=data.category,
        page_path=data.page_path,
        external_key=data.external_key,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if found := existing():
            return found, True
        raise
    return item, False


def feedback_stats(db: Session, workspace_id: int) -> FeedbackStats:
    counts = dict(
        db.execute(
            select(Feedback.status, func.count()).where(Feedback.workspace_id == workspace_id).group_by(Feedback.status)
        ).all()
    )
    return FeedbackStats(
        total=sum(counts.values()), **{status.value: counts.get(status.value, 0) for status in FeedbackStatus}
    )


# --- Analysis -------------------------------------------------------------------


def enqueue_analysis(db: Session, feedback: Feedback, *, retry: bool = False) -> tuple[Analysis, bool]:
    """Return (analysis, created). Starting is idempotent; retrying is allowed only after a failure."""
    current = latest_analysis(db, feedback.id)
    if retry:
        if not current or current.status != AnalysisStatus.FAILED:
            raise Conflict("Only failed analyses can be retried")
    elif current and current.status != AnalysisStatus.FAILED:
        return current, False
    analysis = Analysis(
        feedback_id=feedback.id, version=(current.version + 1) if current else 1, status=AnalysisStatus.QUEUED
    )
    db.add(analysis)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request created the same version first; hand back that one.
        db.rollback()
        return latest_analysis(db, feedback.id), False
    return analysis, True


def run_analysis(analysis_id: int, session_factory: SessionFactory) -> None:
    with session_factory() as db:
        item = db.get(Analysis, analysis_id)
        if not item or item.status != AnalysisStatus.QUEUED:
            return
        item.status = AnalysisStatus.RUNNING
        db.commit()
        try:
            feedback = db.get(Feedback, item.feedback_id)
            candidates = db.scalars(
                select(Feedback)
                .where(Feedback.workspace_id == feedback.workspace_id, Feedback.id != feedback.id)
                .order_by(Feedback.id.desc())
                .limit(200)
            ).all()
            result = analyze(
                feedback.message,
                [
                    {"id": c.id, "message": c.message, "category": c.category, "page_path": c.page_path}
                    for c in candidates
                ],
                feedback.category,
                feedback.page_path,
            )
            item.result_json = json.dumps(result, ensure_ascii=False)
            item.status = AnalysisStatus.SUCCEEDED
        except Exception as exc:  # noqa: BLE001 - any provider failure must become a retryable state
            logger.exception("Analysis %s failed", analysis_id)
            item.error = str(exc)[:500] or exc.__class__.__name__
            item.status = AnalysisStatus.FAILED
        item.finished_at = now()
        db.commit()


def recover_interrupted_analyses(db: Session) -> int:
    """Background tasks are process-local; anything left mid-flight by a restart becomes retryable."""
    stuck = db.scalars(
        select(Analysis).where(Analysis.status.in_([AnalysisStatus.QUEUED, AnalysisStatus.RUNNING]))
    ).all()
    for item in stuck:
        item.status = AnalysisStatus.FAILED
        item.error = "Interrupted by a server restart. Retry to run it again."
        item.finished_at = now()
    db.commit()
    return len(stuck)


# --- Requirements ---------------------------------------------------------------


def existing_requirement_for(db: Session, feedback: Feedback) -> Requirement | None:
    return db.scalar(
        select(Requirement).join(requirement_sources).where(requirement_sources.c.feedback_id == feedback.id)
    )


def create_requirement(db: Session, feedback: Feedback, draft: dict) -> tuple[Requirement, bool]:
    """Create a draft linked to its source feedback. One requirement per feedback item."""
    if found := existing_requirement_for(db, feedback):
        return found, False
    requirement = Requirement(
        workspace_id=feedback.workspace_id,
        title=draft["suggested_title"][:200],
        problem=draft["problem"],
        acceptance_criteria="\n".join(draft["acceptance_criteria"]),
        open_questions="\n".join(draft["open_questions"]),
        status=RequirementStatus.DRAFT,
    )
    db.add(requirement)
    try:
        db.flush()
        db.execute(insert(requirement_sources).values(requirement_id=requirement.id, feedback_id=feedback.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        if found := existing_requirement_for(db, feedback):
            return found, False
        raise
    db.refresh(requirement)
    return requirement, True


def create_requirement_from_analysis(db: Session, feedback: Feedback) -> tuple[Requirement, bool]:
    if found := existing_requirement_for(db, feedback):
        return found, False
    analysis = latest_analysis(db, feedback.id)
    if not analysis or analysis.status != AnalysisStatus.SUCCEEDED or not analysis.result_json:
        raise Conflict("Complete an analysis before creating a draft")
    return create_requirement(db, feedback, json.loads(analysis.result_json))


def update_requirement(db: Session, requirement: Requirement, values: dict) -> Requirement:
    next_status = values.get("status")
    if next_status and next_status not in REQUIREMENT_TRANSITIONS[RequirementStatus(requirement.status)]:
        raise Conflict(f"Cannot move a {requirement.status} requirement to {next_status}")
    for key, value in values.items():
        setattr(requirement, key, value)
    if next_status == RequirementStatus.DELIVERED:
        for source in requirement.sources:
            source.status = FeedbackStatus.RESOLVED
    db.commit()
    db.refresh(requirement)
    return requirement
