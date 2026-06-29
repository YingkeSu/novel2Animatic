"""Scene source router — the single dispatch point for source_type → handler.

Three generation modes are dispatched here instead of inline in the routers:

- ``text_split``    → background task ``run_pipeline_task`` (LLM splits pasted text,
                      then runs the shared media pipeline).
- ``short_fiction`` → background task ``_run_short_fiction_generation`` (LLM invents
                      scenes from a direction, then runs the shared media pipeline).
- ``play_world``    → synchronous ``WorldEngine.step`` (one turn = one scene,
                      returns narration + suggested actions immediately).

The routers keep ONLY HTTP concerns: auth, ownership filtering, request/response
mapping, and the background-vs-sync dispatch model (``asyncio.create_task`` for the
two background sources, inline ``await`` for ``play_world``). The selection of which
handler runs for a given ``source_type`` lives here.

All three sources produce Scene-compatible outputs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Dict

from sqlalchemy import select

from app.models.project import Project
from app.models.scene import Scene
from app.models.task import Task
from app.services.event_bus import event_bus, publish_progress
from app.services.stepfun_client import StepFunClient
from app.services.world_engine import WorldEngine

logger = logging.getLogger(__name__)


class SceneSource(str, Enum):
    """Supported scene source types."""

    TEXT_SPLIT = "text_split"
    SHORT_FICTION = "short_fiction"
    PLAY_WORLD = "play_world"


# Dispatch model per source type. Background sources are kicked off via
# ``asyncio.create_task`` by the router and polled via /progress; the play_world
# source runs synchronously and returns its result in the same request.
_BACKGROUND_SOURCES = frozenset({SceneSource.TEXT_SPLIT, SceneSource.SHORT_FICTION})
_SYNC_SOURCES = frozenset({SceneSource.PLAY_WORLD})


@dataclass
class RouteResult:
    """Metadata describing the handler a source type maps to.

    Kept for backwards compatibility with earlier tests/consumers; the real
    dispatch now happens through :func:`get_generation_kind`,
    :func:`start_background_generation` and :func:`run_play_turn`.
    """

    source: SceneSource
    handler: str  # Module.function path for the handler


def _resolve_source(source_type: str) -> SceneSource:
    """Validate and return the SceneSource for a source type string."""
    try:
        return SceneSource(source_type)
    except ValueError:
        raise ValueError(
            f"Unknown source type: {source_type}. "
            f"Must be one of: {[s.value for s in SceneSource]}"
        )


def route_scenes(source_type: str) -> RouteResult:
    """Route a scene source type to its handler metadata.

    Args:
        source_type: One of "text_split", "short_fiction", "play_world".

    Returns:
        RouteResult with source enum and handler path.

    Raises:
        ValueError: If source_type is unknown.
    """
    source = _resolve_source(source_type)
    handlers = {
        SceneSource.TEXT_SPLIT: "pipeline.run_pipeline_task",
        SceneSource.SHORT_FICTION: "scene_router._run_short_fiction_generation",
        SceneSource.PLAY_WORLD: "world_engine.WorldEngine.step",
    }
    return RouteResult(source=source, handler=handlers[source])


def get_generation_kind(source_type: str) -> str:
    """Return the dispatch model for a source type.

    Args:
        source_type: One of the supported :class:`SceneSource` values.

    Returns:
        ``"background"`` for text_split / short_fiction (router wraps the
        returned coroutine in ``asyncio.create_task``) or ``"sync"`` for
        play_world (router awaits inline).

    Raises:
        ValueError: If source_type is unknown.
    """
    source = _resolve_source(source_type)
    if source in _BACKGROUND_SOURCES:
        return "background"
    if source in _SYNC_SOURCES:
        return "sync"
    # Unreachable: _resolve_source guards against unknown values.
    raise ValueError(f"Unknown source type: {source_type}")


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
    from app.services.pipeline import run_media_pipeline, STORAGE_DIR
    from app.services.scene_generator import SceneGenerator

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
    # Publish the initial split_scenes milestone so SSE subscribers see the
    # run has started (mirrors the text_split publish in run_pipeline_task).
    await publish_progress(project_id, "split_scenes", 10, "running")

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
        # Notify SSE subscribers of the split_scenes failure.
        await publish_progress(
            project_id, "split_scenes", 10, "failed", error_msg=sanitized
        )
        await event_bus.publish(
            str(project_id), "error",
            {"step": "split_scenes", "error": sanitized, "project_id": project_id},
        )
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
        await db.commit()

    logger.info("Short fiction scenes generated for project %d: %d scenes, starting media pipeline",
                project_id, len(gen_result.scenes))

    # Run shared media generation pipeline (steps 2-5).
    try:
        async with async_session() as db:
            project_result = await db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one_or_none()
            if not project:
                return

            project_dir = STORAGE_DIR / str(user_id) / str(project_id)

            scenes_result = await db.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.seq)
            )
            scenes = scenes_result.scalars().all()

            task_result = await db.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one()

            await run_media_pipeline(db, client, project, scenes, project_dir, task)

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
        # Notify SSE subscribers of the media-pipeline failure. task.step reflects
        # how far run_media_pipeline progressed before raising.
        await publish_progress(
            project_id, "error", 0, "failed", error_msg=sanitized
        )
        await event_bus.publish(
            str(project_id), "error",
            {"step": "media_pipeline", "error": sanitized, "project_id": project_id},
        )


def start_background_generation(
    source_type: str,
    *,
    task_id: int | None = None,
    project_id: int,
    user_id: int,
    direction: str | None = None,
    chapter_count: int = 3,
    chars_per_chapter: int = 500,
) -> Awaitable[Any]:
    """Return the background coroutine for a background-dispatched source type.

    The caller (router) is responsible for wrapping the returned coroutine in
    ``asyncio.create_task`` so the HTTP request returns immediately while the
    pipeline runs in-process. This preserves the pre-refactor dispatch model
    where text_split and short_fiction were both kicked off as background tasks.

    Args:
        source_type: ``text_split`` or ``short_fiction``.
        task_id: Required for ``text_split`` (the pipeline reads its task row).
        project_id: Project being generated.
        user_id: Owning user (used for storage path in short_fiction).
        direction: Story direction (short_fiction only).
        chapter_count, chars_per_chapter: short_fiction tuning knobs.

    Returns:
        An awaitable to be scheduled by the router via ``asyncio.create_task``.

    Raises:
        ValueError: If ``source_type`` is not a background source.
    """
    source = _resolve_source(source_type)
    if source not in _BACKGROUND_SOURCES:
        raise ValueError(
            f"source_type {source_type!r} is not a background source; "
            f"use run_play_turn for play_world"
        )

    if source is SceneSource.TEXT_SPLIT:
        if task_id is None:
            raise ValueError("task_id is required for text_split background generation")
        from app.tasks.pipeline import run_pipeline_task
        return run_pipeline_task(task_id)

    # short_fiction
    direction = direction or "默认故事"
    return _run_short_fiction_generation(
        project_id, user_id, direction, chapter_count, chars_per_chapter
    )


async def run_play_turn(
    *,
    project_id: int,
    turn: int,
    raw_input: str,
    context: str,
    client: StepFunClient | None = None,
) -> Dict[str, Any]:
    """Execute a single synchronous play_world turn and persist the scene.

    This is the sync dispatch path: the router awaits it inline and maps the
    returned dict directly to the HTTP response. On a world-engine failure the
    exception propagates to the caller, which is responsible for sanitizing it
    via ``log_play_error`` (preserving #45 error sanitization).

    Args:
        project_id: Project being played.
        turn: 1-based turn number (used as the scene seq).
        raw_input: Player's free-text action for this turn.
        context: World context string (falls back elsewhere if empty).
        client: Optional StepFunClient (a fresh one is constructed if omitted).

    Returns:
        Dict with ``scene_text``, ``suggested_actions``, ``mutation_summary``,
        ``turn`` and ``action_kind`` keys.

    Raises:
        ValueError: If source_type is not play_world (handled by the caller
            before reaching here in the normal router flow).
    """
    if client is None:
        client = StepFunClient()
    llm_fn = _make_llm_fn(client)
    engine = WorldEngine(llm_fn=llm_fn)

    turn_result = await engine.step(
        world_id=project_id,
        turn=turn,
        raw_input=raw_input,
        context=context,
    )

    return {
        "scene_text": turn_result.scene_text,
        "suggested_actions": turn_result.suggested_actions,
        "mutation_summary": turn_result.mutation_summary,
        "turn": turn,
        "action_kind": turn_result.action_kind,
        "_scene_dict": turn_result.to_scene_dict(),
    }
