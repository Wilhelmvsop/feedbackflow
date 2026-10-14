from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import select

from .. import notify, services
from ..deps import DB, CurrentUser
from ..models import Requirement, Task
from ..schemas import RequirementOut, RequirementUpdate, TaskIn, TaskUpdate

router = APIRouter(prefix="/api/requirements", tags=["requirements"])


@router.get("", response_model=list[RequirementOut])
def list_requirements(db: DB, user: CurrentUser):
    return db.scalars(
        select(Requirement).where(Requirement.workspace_id == user.workspace_id).order_by(Requirement.id.desc())
    ).all()


@router.get("/{requirement_id}", response_model=RequirementOut)
def get_requirement(requirement_id: int, db: DB, user: CurrentUser):
    return services.owned_requirement(db, user.workspace_id, requirement_id)


@router.patch("/{requirement_id}", response_model=RequirementOut)
def update_requirement(
    requirement_id: int, data: RequirementUpdate, db: DB, user: CurrentUser, background: BackgroundTasks
):
    requirement = services.owned_requirement(db, user.workspace_id, requirement_id)
    previous = requirement.status
    requirement = services.update_requirement(db, requirement, data.model_dump(exclude_unset=True))
    if requirement.status != previous and notify.enabled():
        background.add_task(notify.publish, notify.requirement_status_changed(user.workspace, requirement, previous))
    return requirement


def _owned_task(db, requirement: Requirement, task_id: int) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.requirement_id == requirement.id))
    if not task:
        raise services.NotFound("Task not found")
    return task


@router.post("/{requirement_id}/tasks", status_code=201, response_model=RequirementOut)
def add_task(requirement_id: int, data: TaskIn, db: DB, user: CurrentUser):
    requirement = services.owned_requirement(db, user.workspace_id, requirement_id)
    requirement.tasks.append(Task(title=data.title))
    db.commit()
    db.refresh(requirement)
    return requirement


@router.patch("/{requirement_id}/tasks/{task_id}", response_model=RequirementOut)
def update_task(requirement_id: int, task_id: int, data: TaskUpdate, db: DB, user: CurrentUser):
    requirement = services.owned_requirement(db, user.workspace_id, requirement_id)
    task = _owned_task(db, requirement, task_id)
    for key, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.delete("/{requirement_id}/tasks/{task_id}", response_model=RequirementOut)
def delete_task(requirement_id: int, task_id: int, db: DB, user: CurrentUser):
    requirement = services.owned_requirement(db, user.workspace_id, requirement_id)
    db.delete(_owned_task(db, requirement, task_id))
    db.commit()
    db.refresh(requirement)
    return requirement
