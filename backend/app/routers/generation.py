"""Scene generation router — handles text_split, short_fiction, play_world."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.scene import Scene
from app.models.task import Task
from app.services.auth import get_current_user
from app.services.scene_generator import SceneGenerator
from app.services.world_engine import WorldEngine
from app.services.stepfun_client import StepFunClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["generation"])


class GenerateRequest(BaseModel):
    source_type: str = "short_fiction"
    chapter_count: int = 3
    chars_per_chapter: int = 500


class PlayRequest(BaseModel):
    raw_input: str
    context: str = ""


def _make_llm_fn(client: StepFunClient, model: str = "step-3.7-flash"):
    """Create an async llm_fn callable from StepFunClient."""
    async def llm_fn(messages, temperature=0.7, **kwargs):
        kwargs.setdefault("max_tokens", 4096)
        return await asyncio.to_thread(
            client.llm_chat, messages, model=model, temperature=temperature, **kwargs
        )
    return llm_fn


async def _run_short_fiction_generation(
    project_id: int, user_id: int, direction: str, chapter_count: int, chars_per_chapter: int
):
    """Background task for short_fiction generation + media pipeline."""
    from app.database import async_session
    from app.services.pipeline import generate_reference_asset, assemble_video, _retry_call
    from app.services.style_engine import get_visual_suffix, get_audio_params
    from app.models.asset import Asset

    client = StepFunClient()
    llm_fn = _make_llm_fn(client)
    gen = SceneGenerator(llm_fn=llm_fn)

    # Create Task early so progress endpoint works during scene generation
    async with async_session() as db:
        task = Task(project_id=project_id, user_id=user_id, status="running", step="split_scenes", progress=10)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    try:
        gen_result = await gen.generate(
            direction=direction,
            chapter_count=chapter_count,
            chars_per_chapter=chars_per_chapter,
        )
    except Exception as e:
        from app.services.errors import log_pipeline_error
        sanitized = log_pipeline_error(e, task_id=task_id, project_id=project_id)
        async with async_session() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if project:
                project.status = "failed"
            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_msg = sanitized
            await db.commit()
        return

    # Save scenes
    async with async_session() as db:
        for scene_data in gen_result.scenes:
            scene = Scene(
                project_id=project_id,
                seq=scene_data.get("seq", 0),
                title=scene_data.get("title", ""),
                text=scene_data.get("text", ""),
                shot_type=scene_data.get("shot_type", "medium"),
                narration=scene_data.get("narration", ""),
                edit_prompt=scene_data.get("edit_prompt", ""),
                instruction=scene_data.get("instruction", ""),
                character=scene_data.get("character", ""),
            )
            db.add(scene)

        # Update task progress to media pipeline phase
        task_result = await db.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one()
        task.step = "generate_refs"
        task.progress = 25
        await db.commit()

    logger.info("Short fiction scenes generated for project %d: %d scenes, starting media pipeline",
                project_id, len(gen_result.scenes))

    # Run media generation pipeline (steps 2-5)
    from pathlib import Path
    STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"

    try:
        async with async_session() as db:
            project_result = await db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one_or_none()
            if not project:
                return

            project_dir = STORAGE_DIR / str(user_id) / str(project_id)
            project_dir.mkdir(parents=True, exist_ok=True)

            scenes_result = await db.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq)
            )
            scenes = scenes_result.scalars().all()

            # Step 2: Generate character reference images
            await generate_reference_asset(db, client, project, scenes, project_dir)

            # Update task progress
            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one()
            task.step = "generate_images"
            task.progress = 40
            await db.commit()

        # Step 3: Generate scene images
        async with async_session() as db:
            scenes_result = await db.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq)
            )
            scenes = scenes_result.scalars().all()

            project_result = await db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one()

            visual_suffix = get_visual_suffix(project.style_visual)
            for scene in scenes:
                img_data = await asyncio.to_thread(
                    _retry_call, client.image_generate,
                    prompt=scene.edit_prompt + visual_suffix,
                    extra_body={"cfg_scale": 1.0, "steps": 8, "seed": 42 + scene.seq},
                    size="1024x1024",
                )
                img_path = project_dir / f"scene_{scene.seq}.png"
                img_path.write_bytes(img_data)
                db.add(Asset(project_id=project_id, scene_id=scene.id, type="image", file_path=str(img_path), file_size=len(img_data)))

            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one()
            task.step = "generate_audio"
            task.progress = 65
            await db.commit()

        # Step 4: Generate TTS audio
        async with async_session() as db:
            scenes_result = await db.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq)
            )
            scenes = scenes_result.scalars().all()

            project_result = await db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one()

            audio_params = get_audio_params(project.style_audio)
            for scene in scenes:
                instruction = (
                    scene.instruction
                    if isinstance(scene.instruction, str) and scene.instruction.strip()
                    else audio_params["instruction"]
                )
                audio_data = await asyncio.to_thread(
                    _retry_call, client.tts,
                    text=scene.narration,
                    voice=audio_params["voice"],
                    extra_body={
                        "volume": audio_params["volume"],
                        "speed": audio_params["speed"],
                        "instruction": instruction,
                    },
                )
                audio_path = project_dir / f"scene_{scene.seq}.mp3"
                audio_path.write_bytes(audio_data)
                db.add(Asset(project_id=project_id, scene_id=scene.id, type="audio", file_path=str(audio_path), file_size=len(audio_data)))

            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one()
            task.step = "assemble_video"
            task.progress = 90
            await db.commit()

        # Step 5: Assemble video
        async with async_session() as db:
            scenes_result = await db.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq)
            )
            scenes = scenes_result.scalars().all()

            video_path = project_dir / "final.mp4"
            await assemble_video(project_dir, scenes, video_path)
            if video_path.exists():
                db.add(Asset(project_id=project_id, type="video", file_path=str(video_path), file_size=video_path.stat().st_size))

            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one()
            task.status = "done"
            task.step = "complete"
            task.progress = 100

            project_result = await db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one()
            project.status = "done"
            await db.commit()

        logger.info("Short fiction pipeline complete for project %d", project_id)

    except Exception as e:
        from app.services.errors import log_pipeline_error
        sanitized = log_pipeline_error(e, task_id=task_id, project_id=project_id)
        async with async_session() as db:
            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_msg = sanitized

            project_result = await db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one_or_none()
            if project:
                project.status = "failed"
            await db.commit()


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

    if project.source_type == "text_split":
        raise HTTPException(status_code=400, detail="text_split uses /run endpoint")

    if project.source_type != "short_fiction":
        raise HTTPException(status_code=400, detail=f"Unsupported source_type: {project.source_type}")

    direction = project.direction or "默认故事"
    project.status = "running"
    await db.commit()

    asyncio.create_task(
        _run_short_fiction_generation(
            project_id, user.id, direction, req.chapter_count, req.chars_per_chapter
        )
    )

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

    if project.source_type != "play_world":
        raise HTTPException(status_code=400, detail="Only play_world projects support /play")

    # Count existing scenes for turn number
    scene_result = await db.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq.desc())
    )
    latest_scene = scene_result.scalars().first()
    turn = (latest_scene.seq + 1) if latest_scene else 1

    context = req.context or project.direction or "未知世界"

    client = StepFunClient()
    llm_fn = _make_llm_fn(client)
    engine = WorldEngine(llm_fn=llm_fn)

    try:
        turn_result = await engine.step(
            world_id=project_id,
            turn=turn,
            raw_input=req.raw_input,
            context=context,
        )
    except Exception as e:
        from app.services.errors import log_play_error
        detail = log_play_error(e, project_id=project_id)
        raise HTTPException(status_code=500, detail=detail)

    # Save scene to DB
    scene_dict = turn_result.to_scene_dict()
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

    return {
        "scene_text": turn_result.scene_text,
        "suggested_actions": turn_result.suggested_actions,
        "mutation_summary": turn_result.mutation_summary,
        "turn": turn,
        "action_kind": turn_result.action_kind,
    }
