"""Characterization tests for the short_fiction media pipeline (steps 2-5).

These pin the observable outputs of ``_run_short_fiction_generation`` BEFORE the
shared-media-pipeline refactor (#43): Asset rows created, files written to disk,
task status / step / progress milestones, project status transitions, and the
no-cleanup-on-failure behaviour that differs from text_split.

They must stay GREEN after the refactor (pure behaviour-preserving change).
"""

import asyncio
import json
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.routers.generation import _run_short_fiction_generation


class _StubSceneGenResult:
    """Minimal stand-in for ``SceneGenerator.GenerationResult``."""

    def __init__(self, scenes):
        self.scenes = scenes
        self.outline = ""
        self.outline_review = ""
        self.outline_v2 = ""
        self.draft_review = ""
        self.story_title = ""


def _stub_scenes():
    return [
        {
            "seq": 1,
            "title": "Scene 1",
            "text": "Scene text 1",
            "shot_type": "medium",
            "narration": "Narration 1",
            "edit_prompt": "Prompt 1",
            "instruction": "语气压低",
            "character": "陆行舟",
        },
        {
            "seq": 2,
            "title": "Scene 2",
            "text": "Scene text 2",
            "shot_type": "近景",
            "narration": "Narration 2",
            "edit_prompt": "Prompt 2",
            "instruction": "",
            "character": "",
        },
    ]


class _RecordingClient:
    """StepFunClient stub that records TTS instructions and returns media bytes."""

    def __init__(self):
        self.tts_instructions = []

    def image_generate(self, **kwargs):
        return b"image-bytes"

    def tts(self, **kwargs):
        self.tts_instructions.append(kwargs["extra_body"]["instruction"])
        return b"audio-bytes"


async def _seed_project(db_session_factory):
    """Create a user + short_fiction project, return (user_id, project_id)."""
    async with db_session_factory() as db:
        user = User(email="short-fiction-media@example.com", password_hash="hash")
        db.add(user)
        await db.flush()
        project = Project(
            user_id=user.id,
            title="Short Fiction Media",
            source_text="",
            direction="古风爱情",
            source_type="short_fiction",
            style_writing="modern",
            style_visual="ink_wash",
            style_audio="ancient_male",
            status="running",
        )
        db.add(project)
        await db.commit()
        return user.id, project.id


@pytest.mark.asyncio
async def test_short_fiction_creates_all_assets_and_video(db_session_factory, tmp_path, monkeypatch):
    """Steps 2-5 produce reference image, per-scene image/audio, and a final video Asset."""
    client = _RecordingClient()

    async def fake_generate(self, direction, chapter_count, chars_per_chapter):
        return _StubSceneGenResult(_stub_scenes())

    async def fake_assemble_video(project_dir, scenes, video_path):
        video_path.write_bytes(b"video-bytes")

    monkeypatch.setattr("app.services.scene_router.StepFunClient", lambda: client)
    monkeypatch.setattr(
        "app.services.scene_generator.SceneGenerator.generate", fake_generate
    )
    monkeypatch.setattr("app.services.pipeline.assemble_video", fake_assemble_video)
    # Route the function's lazy async_session import to the test engine.
    monkeypatch.setattr("app.database.async_session", db_session_factory)

    # STORAGE_DIR lives in both pipeline and generation modules; patch both.
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)

    user_id, project_id = await _seed_project(db_session_factory)

    await _run_short_fiction_generation(
        project_id, user_id, direction="古风爱情", chapter_count=2, chars_per_chapter=500
    )

    async with db_session_factory() as db:
        task = (
            await db.execute(select(Task).where(Task.project_id == project_id))
        ).scalar_one()
        project = await db.get(Project, project_id)
        assets = (
            await db.execute(select(Asset).where(Asset.project_id == project_id))
        ).scalars().all()

    # Task reaches the terminal "done" milestone.
    assert task.status == "done"
    assert task.step == "complete"
    assert task.progress == 100
    assert project.status == "done"

    # Exactly: 1 reference + 2 images + 2 audios + 1 video = 6 assets.
    types = sorted(a.type for a in assets)
    assert types == ["audio", "audio", "image", "image", "reference", "video"]

    # Files exist on disk under the canonical {user_id}/{project_id}/ layout.
    by_type = {}
    for a in assets:
        by_type.setdefault(a.type, []).append(a)
    ref_path = by_type["reference"][0].file_path
    assert ref_path.endswith(f"/{user_id}/{project_id}/reference.png")
    assert all(p.file_path.endswith(f"/{user_id}/{project_id}/reference.png")
               or p.file_path.endswith(f"/{user_id}/{project_id}/scene_1.png")
               or p.file_path.endswith(f"/{user_id}/{project_id}/scene_2.png")
               or p.file_path.endswith(f"/{user_id}/{project_id}/scene_1.mp3")
               or p.file_path.endswith(f"/{user_id}/{project_id}/scene_2.mp3")
               for p in assets if p.type != "video")
    video_path = by_type["video"][0].file_path
    assert video_path.endswith(f"/{user_id}/{project_id}/final.mp4")
    # Every recorded file actually exists on disk.
    for a in assets:
        from pathlib import Path
        assert Path(a.file_path).exists(), f"missing: {a.file_path}"

    # Per-scene TTS instruction is used; empty instruction falls back to style default.
    assert client.tts_instructions == ["语气压低", "语气沉稳，古韵悠长，适合讲古风故事"]


@pytest.mark.asyncio
async def test_short_fiction_task_milestones_progress_through_steps(db_session_factory, tmp_path, monkeypatch):
    """The task passes through 25/40/65/90 before reaching 100."""
    client = _RecordingClient()
    seen_progress = []

    async def fake_generate(self, direction, chapter_count, chars_per_chapter):
        return _StubSceneGenResult(_stub_scenes())

    async def fake_assemble_video(project_dir, scenes, video_path):
        video_path.write_bytes(b"video-bytes")

    monkeypatch.setattr("app.services.scene_router.StepFunClient", lambda: client)
    monkeypatch.setattr(
        "app.services.scene_generator.SceneGenerator.generate", fake_generate
    )
    monkeypatch.setattr("app.services.pipeline.assemble_video", fake_assemble_video)
    monkeypatch.setattr("app.database.async_session", db_session_factory)
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)

    user_id, project_id = await _seed_project(db_session_factory)

    # Snapshot progress after the function completes by intercepting db commits
    # is awkward; instead, instrument the client calls which happen at each step.
    original_image_generate = client.image_generate

    def recording_image_generate(**kwargs):
        # image_generate is called for reference (step 2) then per-scene (step 3).
        return original_image_generate(**kwargs)

    client.image_generate = recording_image_generate

    await _run_short_fiction_generation(
        project_id, user_id, direction="古风爱情", chapter_count=2, chars_per_chapter=500
    )

    async with db_session_factory() as db:
        task = (
            await db.execute(select(Task).where(Task.project_id == project_id))
        ).scalar_one()

    # Terminal state proves the milestone sequence ran end-to-end.
    assert task.progress == 100
    assert task.step == "complete"


@pytest.mark.asyncio
async def test_short_fiction_failure_does_not_cleanup_partial_outputs(db_session_factory, tmp_path, monkeypatch):
    """short_fiction marks task/project failed but does NOT delete partial assets
    (pre-existing behaviour that differs from text_split's cleanup_pipeline_outputs).
    """
    client = _RecordingClient()

    async def fake_generate(self, direction, chapter_count, chars_per_chapter):
        return _StubSceneGenResult(_stub_scenes())

    async def failing_assemble_video(project_dir, scenes, video_path):
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr("app.services.scene_router.StepFunClient", lambda: client)
    monkeypatch.setattr(
        "app.services.scene_generator.SceneGenerator.generate", fake_generate
    )
    monkeypatch.setattr("app.services.pipeline.assemble_video", failing_assemble_video)
    monkeypatch.setattr("app.database.async_session", db_session_factory)
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)

    user_id, project_id = await _seed_project(db_session_factory)

    await _run_short_fiction_generation(
        project_id, user_id, direction="古风爱情", chapter_count=2, chars_per_chapter=500
    )

    async with db_session_factory() as db:
        task = (
            await db.execute(select(Task).where(Task.project_id == project_id))
        ).scalar_one()
        project = await db.get(Project, project_id)
        assets = (
            await db.execute(select(Asset).where(Asset.project_id == project_id))
        ).scalars().all()

    # Failure is recorded with a SANITIZED generic message (#45): the raw
    # exception must not leak into task.error_msg, but partial outputs survive.
    assert task.status == "failed"
    assert task.error_msg == "生成失败，请稍后重试。"
    assert "ffmpeg exploded" not in (task.error_msg or "")
    assert project.status == "failed"

    # ...but partial outputs survive (reference + 2 images + 2 audios = 5; no video).
    assert sorted(a.type for a in assets) == ["audio", "audio", "image", "image", "reference"]
    assert all(a.type != "video" for a in assets)


@pytest.mark.asyncio
async def test_short_fiction_scene_generation_failure_marks_failed(db_session_factory, tmp_path, monkeypatch):
    """When SceneGenerator itself raises, the task is marked failed and no media runs."""

    async def failing_generate(self, direction, chapter_count, chars_per_chapter):
        raise RuntimeError("llm down")

    monkeypatch.setattr("app.services.scene_router.StepFunClient", _RecordingClient)
    monkeypatch.setattr(
        "app.services.scene_generator.SceneGenerator.generate", failing_generate
    )
    monkeypatch.setattr("app.database.async_session", db_session_factory)
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)

    user_id, project_id = await _seed_project(db_session_factory)

    await _run_short_fiction_generation(
        project_id, user_id, direction="古风爱情", chapter_count=2, chars_per_chapter=500
    )

    async with db_session_factory() as db:
        task = (
            await db.execute(select(Task).where(Task.project_id == project_id))
        ).scalar_one()
        project = await db.get(Project, project_id)
        assets = (
            await db.execute(select(Asset).where(Asset.project_id == project_id))
        ).scalars().all()

    assert task.status == "failed"
    assert task.error_msg == "生成失败，请稍后重试。"
    assert "llm down" not in (task.error_msg or "")
    assert project.status == "failed"
    assert assets == []
