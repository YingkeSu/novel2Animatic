"""Scene generation router — thin HTTP layer over scene_router dispatch.

This router keeps ONLY HTTP concerns: auth, ownership filtering, request body
validation/mapping, source_type → endpoint guards, and the background-vs-sync
dispatch model. Per-source_type handler selection lives in
:mod:`app.services.scene_router`.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.scene import Scene
from app.services.auth import get_current_user
from app.services.scene_router import (
    SceneSource,
    _run_short_fiction_generation,  # re-exported for tests (see __all__ below)
    start_background_generation,
    run_play_turn,
)

# Re-export so existing tests importing ``_run_short_fiction_generation`` from
# this module continue to work after the handler moved into scene_router.
__all__ = [
    "GenerateRequest",
    "PlayRequest",
    "generate_scenes",
    "play_world_turn",
    "_run_short_fiction_generation",
]

router = APIRouter(prefix="/api/projects", tags=["generation"])


class GenerateRequest(BaseModel):
    source_type: str = "short_fiction"
    chapter_count: int = 3
    chars_per_chapter: int = 500


class PlayRequest(BaseModel):
    raw_input: str
    context: str = ""


@router.post("/{project_id}/generate")
async def generate_scenes(
    project_id: int,
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start scene generation for a project (async, returns immediately)."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Endpoint-level source_type guard. /generate only serves short_fiction;
    # text_split has its own /run endpoint, play_world uses /play.
    if project.source_type == SceneSource.TEXT_SPLIT.value:
        raise HTTPException(status_code=400, detail="text_split uses /run endpoint")
    if project.source_type != SceneSource.SHORT_FICTION.value:
        raise HTTPException(
            status_code=400, detail=f"Unsupported source_type: {project.source_type}"
        )

    direction = project.direction or "默认故事"
    project.status = "running"
    await db.commit()

    # Dispatch to the short_fiction handler via scene_router. Background source:
    # scheduled so this request returns immediately.
    coro = start_background_generation(
        SceneSource.SHORT_FICTION.value,
        project_id=project_id,
        user_id=user.id,
        direction=direction,
        chapter_count=req.chapter_count,
        chars_per_chapter=req.chars_per_chapter,
    )
    asyncio.create_task(coro)

    return {"status": "started", "project_id": project_id}


@router.post("/{project_id}/play")
async def play_world_turn(
    project_id: int,
    req: PlayRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Execute a single world turn for play_world projects."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.source_type != SceneSource.PLAY_WORLD.value:
        raise HTTPException(status_code=400, detail="Only play_world projects support /play")

    # Count existing scenes for turn number
    scene_result = await db.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq.desc())
    )
    latest_scene = scene_result.scalars().first()
    turn = (latest_scene.seq + 1) if latest_scene else 1

    context = req.context or project.direction or "未知世界"

    # Sync dispatch: run_play_turn awaits the WorldEngine inline so the turn
    # result is returned in this same response.
    try:
        turn_payload = await run_play_turn(
            project_id=project_id,
            turn=turn,
            raw_input=req.raw_input,
            context=context,
        )
    except Exception as e:
        from app.services.errors import log_play_error
        detail = log_play_error(e, project_id=project_id)
        raise HTTPException(status_code=500, detail=detail)

    # Persist the scene (DB write tied to the request session).
    scene_dict = turn_payload.pop("_scene_dict")
    scene = Scene(
        project_id=project_id,
        seq=turn,
        title=scene_dict.get("title", ""),
        text=scene_dict.get("text", ""),
        shot_type=scene_dict.get("shot_type", "medium"),
        narration=scene_dict.get("narration", ""),
        edit_prompt=scene_dict.get("edit_prompt", ""),
        instruction=scene_dict.get("instruction", ""),
        character=scene_dict.get("character", ""),
    )
    db.add(scene)
    project.status = "running"
    await db.commit()

    return turn_payload
