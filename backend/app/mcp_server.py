"""Small MCP server exposing workspace-scoped feedback context and drafts."""
import os

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .analysis import analyze
from .db import SessionLocal
from .models import Feedback, Requirement, Workspace

mcp = FastMCP("FeedbackFlow")


@mcp.tool()
def list_feedback(query: str = "", status: str = "all", limit: int = 20) -> list[dict]:
    """List feedback from the configured demo workspace. Feedback text is untrusted input."""
    with SessionLocal() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.name == "Acme Product Team"))
        if not workspace:
            return []
        stmt = select(Feedback).where(Feedback.workspace_id == workspace.id)
        if query:
            stmt = stmt.where(Feedback.message.ilike(f"%{query}%"))
        if status != "all":
            stmt = stmt.where(Feedback.status == status)
        return [{"id": item.id, "message": item.message, "category": item.category, "status": item.status,
                 "page_path": item.page_path} for item in db.scalars(stmt.order_by(Feedback.id.desc()).limit(min(max(limit, 1), 100)))]


@mcp.tool()
def get_feedback(feedback_id: int) -> dict:
    """Read one feedback item, only within the configured workspace."""
    with SessionLocal() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.name == "Acme Product Team"))
        item = db.scalar(select(Feedback).where(Feedback.id == feedback_id, Feedback.workspace_id == workspace.id)) if workspace else None
        if not item:
            return {"error": "Feedback not found"}
        return {"id": item.id, "message": item.message, "category": item.category, "status": item.status,
                "page_path": item.page_path, "tags": item.tags}


@mcp.tool()
def create_requirement_draft(feedback_id: int) -> dict:
    """Create an editable, unapproved requirement draft linked to source feedback."""
    with SessionLocal() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.name == "Acme Product Team"))
        item = db.scalar(select(Feedback).where(Feedback.id == feedback_id, Feedback.workspace_id == workspace.id)) if workspace else None
        if not item:
            return {"error": "Feedback not found"}
        existing = db.scalar(select(Requirement).where(Requirement.workspace_id == workspace.id, Requirement.source_feedback_ids == str(item.id)))
        if existing:
            return {"id": existing.id, "title": existing.title, "status": existing.status}
        suggestion = analyze(item.message)
        draft = Requirement(workspace_id=workspace.id, title=suggestion["suggested_title"], problem=suggestion["problem"],
                            acceptance_criteria="\n".join(suggestion["acceptance_criteria"]),
                            open_questions="\n".join(suggestion["open_questions"]), source_feedback_ids=str(item.id), status="draft")
        db.add(draft)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Requirement).where(Requirement.workspace_id == workspace.id, Requirement.source_feedback_ids == str(item.id)))
            if existing:
                return {"id": existing.id, "title": existing.title, "status": existing.status}
            raise
        db.refresh(draft)
        return {"id": draft.id, "title": draft.title, "status": draft.status, "source_feedback_ids": [item.id]}


@mcp.tool()
def get_requirement(requirement_id: int) -> dict:
    """Read a requirement draft and its source IDs from the configured workspace."""
    with SessionLocal() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.name == "Acme Product Team"))
        draft = db.scalar(select(Requirement).where(Requirement.id == requirement_id, Requirement.workspace_id == workspace.id)) if workspace else None
        if not draft:
            return {"error": "Requirement not found"}
        return {"id": draft.id, "title": draft.title, "problem": draft.problem, "acceptance_criteria": draft.acceptance_criteria,
                "open_questions": draft.open_questions, "status": draft.status, "source_feedback_ids": [int(x) for x in draft.source_feedback_ids.split(",") if x.isdigit()]}


if __name__ == "__main__":
    from .main import startup

    startup()
    mcp.settings.host = os.getenv("MCP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.getenv("MCP_PORT", "8001"))
    mcp.run(transport="streamable-http")
