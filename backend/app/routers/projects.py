"""Projects router."""

from contextlib import suppress
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.scene import Scene
from app.models.asset import Asset
from app.models.task import Task
from app.schemas import ProjectCreate, ProjectResponse, ProjectDetailResponse, SceneResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"
TERMINAL_TASK_STATUSES = {"done", "failed"}


@router.post("", response_model=ProjectResponse)
async def create_project(
    req: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = Project(
        user_id=user.id,
        title=req.title,
        source_text=req.source_text,
        source_type=req.source_type,
        direction=req.direction,
        style_writing=req.style_writing,
        style_visual=req.style_visual,
        style_audio=req.style_audio,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    if not projects:
        return projects

    task_result = await db.execute(
        select(Task.project_id, Task.status, Task.error_msg)
        .where(
            Task.project_id.in_([project.id for project in projects]),
        )
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    latest_task_by_project = {}
    for project_id, status, error_msg in task_result.all():
        latest_task_by_project.setdefault(project_id, (status, error_msg))

    for project in projects:
        latest_task = latest_task_by_project.get(project.id)
        project.latest_error_msg = latest_task[1] if latest_task and latest_task[0] == "failed" else None

    return projects


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == user.id)
        .options(selectinload(Project.scenes))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.scenes.sort(key=lambda scene: scene.seq)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_result = await db.execute(
        select(Task)
        .where(Task.project_id == project_id, Task.user_id == user.id)
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    latest_task = task_result.scalars().first()
    if latest_task and latest_task.status not in TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=409, detail="Pipeline is still running")

    # Delete in order: tasks, assets, scenes, then project
    await db.execute(delete(Task).where(Task.project_id == project_id))
    await db.execute(delete(Asset).where(Asset.project_id == project_id))
    await db.execute(delete(Scene).where(Scene.project_id == project_id))
    await db.delete(project)
    await db.commit()

    project_dir = STORAGE_DIR / str(project.user_id) / str(project.id)
    with suppress(FileNotFoundError, NotADirectoryError):
        shutil.rmtree(project_dir)

    return {"detail": "deleted"}
