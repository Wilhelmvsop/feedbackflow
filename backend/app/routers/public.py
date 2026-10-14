"""Unauthenticated intake used by the embeddable widget."""

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from .. import notify
from ..deps import DB, public_feedback_limiter
from ..schemas import FeedbackIn, FeedbackSubmitted
from ..services import submit_feedback, workspace_by_slug

router = APIRouter(prefix="/api/public", tags=["public"])


@router.post(
    "/{workspace_slug}/feedback",
    status_code=201,
    response_model=FeedbackSubmitted,
    dependencies=[Depends(public_feedback_limiter)],
)
def create_feedback(workspace_slug: str, data: FeedbackIn, response: Response, db: DB, background: BackgroundTasks):
    workspace = workspace_by_slug(db, workspace_slug)
    item, duplicate = submit_feedback(db, workspace, data)
    if duplicate:
        response.status_code = 200
    elif notify.enabled():
        background.add_task(notify.publish, notify.feedback_created(workspace, item))
    return FeedbackSubmitted(id=item.id, status=item.status, duplicate=duplicate)
