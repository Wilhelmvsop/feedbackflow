import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Feedback, FeedbackCategory, FeedbackStatus, User, Workspace
from .security import hash_password

logger = logging.getLogger(__name__)


def seed_demo(db: Session) -> None:
    """Create the demo workspace, account, and sample feedback once."""
    if db.scalar(select(User).where(User.email == settings.demo_email)):
        return
    workspace = db.scalar(select(Workspace).where(Workspace.slug == settings.demo_workspace_slug))
    if not workspace:
        workspace = Workspace(slug=settings.demo_workspace_slug, name="Acme Product Team")
        db.add(workspace)
        db.flush()
    db.add(
        User(workspace_id=workspace.id, email=settings.demo_email, password_hash=hash_password(settings.demo_password))
    )
    db.add_all(
        [
            Feedback(
                workspace_id=workspace.id,
                category=FeedbackCategory.USABILITY,
                page_path="/reports/import",
                status=FeedbackStatus.NEW,
                tags="upload,progress",
                message="Uploading a 40 MB report is very slow, and I can't tell whether it finished.",
            ),
            Feedback(
                workspace_id=workspace.id,
                category=FeedbackCategory.BUG,
                page_path="/reports/import",
                status=FeedbackStatus.TRIAGED,
                tags="import,status",
                message="The import spinner stays on screen even after the file appears in my reports.",
            ),
            Feedback(
                workspace_id=workspace.id,
                category=FeedbackCategory.FEATURE,
                page_path="/analytics",
                status=FeedbackStatus.NEW,
                tags="exports",
                message="Would love to export a monthly usage summary as CSV.",
            ),
        ]
    )
    db.commit()
    logger.info("Seeded demo workspace %r", settings.demo_workspace_slug)
