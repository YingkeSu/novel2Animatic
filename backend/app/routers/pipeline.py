"""Pipeline router - trigger and monitor pipeline execution."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.scene import Scene
from app.models.asset import Asset
from app.schemas import ProgressResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["pipeline"])
TERMINAL_TASK_STATUSES = {"done", "failed"}


@router.post("/{project_id}/run")
async def run_pipeline(
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
        raise HTTPException(status_code=409, detail="Pipeline already running")

    # Clean up old data if retrying (assets first due to scene_id FK)
    if latest_task and latest_task.status in TERMINAL_TASK_STATUSES:
        await db.execute(delete(Asset).where(Asset.project_id == project_id))
        await db.execute(delete(Scene).where(Scene.project_id == project_id))
        await db.commit()

    task = Task(project_id=project_id, user_id=user.id, status="pending", step="queued", progress=0)
    db.add(task)
    project.status = "running"
    await db.commit()
    await db.refresh(task)

    from app.tasks.pipeline import run_pipeline_task
    asyncio.create_task(run_pipeline_task(task.id))

    return {"task_id": task.id, "status": "pending"}


@router.get("/{project_id}/progress")
async def get_progress(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .where(Task.project_id == project_id, Task.user_id == user.id)
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    task = result.first()
    if not task:
        raise HTTPException(status_code=404, detail="No task found")

    task = task[0]
    return ProgressResponse(
        status=task.status,
        step=task.step,
        progress=task.progress,
        error_msg=task.error_msg,
    )
