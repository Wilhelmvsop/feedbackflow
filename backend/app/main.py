import hashlib
import hmac
import json
import secrets
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .analysis import analyze, dumps
from .config import CORS_ORIGINS, DEMO_PASSWORD
from .db import Base, SessionLocal, engine, get_db
from .models import Analysis, Feedback, Requirement, Task, Token, User, Workspace
from .schemas import FeedbackIn, FeedbackUpdate, LoginIn, RequirementUpdate, TaskIn

app = FastAPI(title="FeedbackFlow API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, encoded: str) -> bool:
    salt_hex, expected = encoded.split(":", 1)
    actual = password_hash(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
    return hmac.compare_digest(actual, expected)


def seed_demo():
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "demo@feedbackflow.local")):
            return
        workspace = Workspace(name="Acme Product Team")
        db.add(workspace)
        db.flush()
        user = User(workspace_id=workspace.id, email="demo@feedbackflow.local", password_hash=password_hash(DEMO_PASSWORD))
        db.add(user)
        db.flush()
        samples = [
            Feedback(workspace_id=workspace.id, message="Uploading a 40 MB report is very slow, and I can't tell whether it finished.", category="usability", page_path="/reports/import", status="new", tags="upload,progress"),
            Feedback(workspace_id=workspace.id, message="The import spinner stays on screen even after the file appears in my reports.", category="bug", page_path="/reports/import", status="triaged", tags="import,status"),
            Feedback(workspace_id=workspace.id, message="Would love to export a monthly usage summary as CSV.", category="feature", page_path="/analytics", status="new", tags="exports"),
        ]
        db.add_all(samples)
        db.commit()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    seed_demo()


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to continue")
    token = db.scalar(select(Token).where(Token.value == authorization[7:]))
    user = db.get(User, token.user_id) if token else None
    if not user:
        raise HTTPException(401, "Invalid session")
    return user


def owned_feedback(db: Session, user: User, feedback_id: int) -> Feedback:
    item = db.scalar(select(Feedback).where(Feedback.id == feedback_id, Feedback.workspace_id == user.workspace_id))
    if not item:
        raise HTTPException(404, "Feedback not found")
    return item


def owned_requirement(db: Session, user: User, requirement_id: int) -> Requirement:
    item = db.scalar(select(Requirement).where(Requirement.id == requirement_id, Requirement.workspace_id == user.workspace_id))
    if not item:
        raise HTTPException(404, "Requirement not found")
    return item


def feedback_json(item: Feedback, latest: Analysis | None = None):
    result = {"id": item.id, "message": item.message, "category": item.category, "page_path": item.page_path,
              "status": item.status, "tags": item.tags, "assignee": item.assignee, "created_at": item.created_at.isoformat()}
    result["analysis"] = {"id": latest.id, "status": latest.status, "result": json.loads(latest.result_json) if latest.result_json else None,
                          "error": latest.error, "version": latest.version} if latest else None
    return result


def run_analysis(analysis_id: int):
    with SessionLocal() as db:
        item = db.get(Analysis, analysis_id)
        if not item or item.status != "queued":
            return
        item.status = "running"
        db.commit()
        try:
            feedback = db.get(Feedback, item.feedback_id)
            candidates = db.scalars(select(Feedback).where(Feedback.workspace_id == feedback.workspace_id, Feedback.id != feedback.id)).all()
            item.result_json = dumps(analyze(feedback.message, [{"id": candidate.id, "message": candidate.message,
                                                                "category": candidate.category, "page_path": candidate.page_path}
                                                               for candidate in candidates], feedback.category, feedback.page_path))
            item.status = "succeeded"
        except Exception as exc:
            item.error = str(exc)[:500]
            item.status = "failed"
        db.commit()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    value = secrets.token_urlsafe(32)
    db.add(Token(user_id=user.id, value=value))
    db.commit()
    workspace = db.get(Workspace, user.workspace_id)
    return {"token": value, "user": {"email": user.email}, "workspace": {"id": workspace.id, "name": workspace.name}}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"email": user.email, "workspace": db.get(Workspace, user.workspace_id).name}


@app.post("/api/auth/logout", status_code=204)
def logout(authorization: str = Header(), db: Session = Depends(get_db), user: User = Depends(current_user)):
    token_value = authorization[7:]
    token = db.scalar(select(Token).where(Token.value == token_value, Token.user_id == user.id))
    if token:
        db.delete(token)
        db.commit()


@app.post("/api/feedback", status_code=201)
def create_feedback(data: FeedbackIn, response: Response, db: Session = Depends(get_db)):
    workspace = db.scalar(select(Workspace).where(Workspace.name == "Acme Product Team"))
    if not workspace:
        raise HTTPException(503, "Feedback workspace is not configured")
    if data.external_key:
        existing = db.scalar(select(Feedback).where(Feedback.workspace_id == workspace.id, Feedback.external_key == data.external_key))
        if existing:
            response.status_code = 200
            return {"id": existing.id, "status": existing.status, "duplicate": True}
    item = Feedback(workspace_id=workspace.id, message=data.message.strip(), category=data.category,
                    page_path=data.page_path, external_key=data.external_key)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Feedback).where(Feedback.workspace_id == workspace.id, Feedback.external_key == data.external_key)) if data.external_key else None
        if existing:
            response.status_code = 200
            return {"id": existing.id, "status": existing.status, "duplicate": True}
        raise
    db.refresh(item)
    return {"id": item.id, "status": item.status, "duplicate": False}


@app.get("/api/feedback")
def list_feedback(q: str = "", status: str = "all", category: str = "all", db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Feedback).where(Feedback.workspace_id == user.workspace_id)
    if q:
        stmt = stmt.where(or_(Feedback.message.ilike(f"%{q}%"), Feedback.tags.ilike(f"%{q}%")))
    if status != "all":
        stmt = stmt.where(Feedback.status == status)
    if category != "all":
        stmt = stmt.where(Feedback.category == category)
    items = db.scalars(stmt.order_by(Feedback.id.desc())).all()
    return [feedback_json(item, db.scalar(select(Analysis).where(Analysis.feedback_id == item.id).order_by(Analysis.version.desc()))) for item in items]


@app.get("/api/feedback/{feedback_id}")
def get_feedback(feedback_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = owned_feedback(db, user, feedback_id)
    latest = db.scalar(select(Analysis).where(Analysis.feedback_id == item.id).order_by(Analysis.version.desc()))
    return feedback_json(item, latest)


@app.patch("/api/feedback/{feedback_id}")
def update_feedback(feedback_id: int, data: FeedbackUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = owned_feedback(db, user, feedback_id)
    values = data.model_dump(exclude_unset=True)
    if "status" in values and values["status"] not in ("new", "triaged", "in_progress", "resolved"):
        raise HTTPException(422, "Invalid feedback status")
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    latest = db.scalar(select(Analysis).where(Analysis.feedback_id == item.id).order_by(Analysis.version.desc()))
    return feedback_json(item, latest)


@app.post("/api/feedback/{feedback_id}/analysis", status_code=202)
def start_analysis(feedback_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = owned_feedback(db, user, feedback_id)
    existing = db.scalar(select(Analysis).where(Analysis.feedback_id == item.id).order_by(Analysis.version.desc()))
    if existing and existing.status in ("queued", "running", "succeeded"):
        return {"analysis_id": existing.id, "status": existing.status, "version": existing.version}
    version = (existing.version + 1) if existing else 1
    analysis = Analysis(feedback_id=item.id, version=version, status="queued")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    background.add_task(run_analysis, analysis.id)
    return {"analysis_id": analysis.id, "status": analysis.status, "version": analysis.version}


@app.post("/api/feedback/{feedback_id}/analysis/retry", status_code=202)
def retry_analysis(feedback_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_feedback(db, user, feedback_id)
    existing = db.scalar(select(Analysis).where(Analysis.feedback_id == feedback_id).order_by(Analysis.version.desc()))
    if not existing or existing.status != "failed":
        raise HTTPException(409, "Only failed analyses can be retried")
    retry = Analysis(feedback_id=feedback_id, version=existing.version + 1, status="queued")
    db.add(retry)
    db.commit()
    db.refresh(retry)
    background.add_task(run_analysis, retry.id)
    return {"analysis_id": retry.id, "status": retry.status, "version": retry.version}


@app.post("/api/feedback/{feedback_id}/requirement", status_code=201)
def create_requirement(feedback_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = owned_feedback(db, user, feedback_id)
    analysis = db.scalar(select(Analysis).where(Analysis.feedback_id == item.id).order_by(Analysis.version.desc()))
    if not analysis or analysis.status != "succeeded" or not analysis.result_json:
        raise HTTPException(409, "Complete an analysis before creating a draft")
    draft = json.loads(analysis.result_json)
    existing = db.scalar(select(Requirement).where(Requirement.workspace_id == user.workspace_id, Requirement.source_feedback_ids == str(item.id)))
    if existing:
        return {"id": existing.id, "status": existing.status, "duplicate": True}
    req = Requirement(workspace_id=user.workspace_id, title=draft["suggested_title"], problem=draft["problem"],
                      acceptance_criteria="\n".join(draft["acceptance_criteria"]), open_questions="\n".join(draft["open_questions"]), source_feedback_ids=str(item.id))
    db.add(req)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Requirement).where(Requirement.workspace_id == user.workspace_id, Requirement.source_feedback_ids == str(item.id)))
        if existing:
            return {"id": existing.id, "status": existing.status, "duplicate": True}
        raise
    db.refresh(req)
    return requirement_json(req, db)


def requirement_json(req: Requirement, db: Session):
    source_ids = [int(value) for value in req.source_feedback_ids.split(",") if value.strip().isdigit()]
    return {"id": req.id, "title": req.title, "problem": req.problem, "acceptance_criteria": req.acceptance_criteria,
            "open_questions": req.open_questions, "status": req.status, "source_feedback_ids": source_ids,
            "tasks": [{"id": t.id, "title": t.title, "done": t.done} for t in db.scalars(select(Task).where(Task.requirement_id == req.id))]}


@app.get("/api/requirements")
def list_requirements(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [requirement_json(r, db) for r in db.scalars(select(Requirement).where(Requirement.workspace_id == user.workspace_id).order_by(Requirement.id.desc()))]


@app.get("/api/requirements/{requirement_id}")
def get_requirement(requirement_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return requirement_json(owned_requirement(db, user, requirement_id), db)


@app.patch("/api/requirements/{requirement_id}")
def update_requirement(requirement_id: int, data: RequirementUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    req = owned_requirement(db, user, requirement_id)
    values = data.model_dump(exclude_unset=True)
    if "status" in values and values["status"] not in ("draft", "confirmed", "delivered"):
        raise HTTPException(422, "Invalid requirement status")
    next_status = values.get("status")
    allowed_transitions = {"draft": {"draft", "confirmed"}, "confirmed": {"confirmed", "delivered"}, "delivered": {"delivered"}}
    if next_status and next_status not in allowed_transitions[req.status]:
        raise HTTPException(409, f"Cannot move a {req.status} requirement to {next_status}")
    for key, value in values.items():
        setattr(req, key, value)
    db.commit()
    if req.status == "delivered":
        for raw_id in req.source_feedback_ids.split(","):
            if raw_id.strip().isdigit():
                source = db.scalar(select(Feedback).where(Feedback.id == int(raw_id), Feedback.workspace_id == user.workspace_id))
                if source:
                    source.status = "resolved"
        db.commit()
    return requirement_json(req, db)


@app.post("/api/requirements/{requirement_id}/tasks", status_code=201)
def add_task(requirement_id: int, data: TaskIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    req = owned_requirement(db, user, requirement_id)
    task = Task(requirement_id=req.id, title=data.title)
    db.add(task)
    db.commit()
    return requirement_json(req, db)


@app.patch("/api/requirements/{requirement_id}/tasks/{task_id}")
def toggle_task(requirement_id: int, task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    req = owned_requirement(db, user, requirement_id)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.requirement_id == req.id))
    if not task:
        raise HTTPException(404, "Task not found")
    task.done = not task.done
    db.commit()
    return requirement_json(req, db)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "static", html=True), name="static")
