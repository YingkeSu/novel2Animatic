"""Tests for pipeline scene splitting (with mocked LLM)."""

from types import SimpleNamespace
import pytest
import json
from unittest.mock import MagicMock
from sqlalchemy import select

from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.models.task import Task
from app.models.user import User
from app.services.pipeline import assemble_video, run_pipeline_task, split_scenes_sync


def test_split_scenes_json_response():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = json.dumps({
        "scenes": [
            {
                "title": "Scene 1",
                "text": "Test text",
                "shot_type": "中景",
                "narration": "Narration 1",
                "edit_prompt": "Prompt 1",
                "instruction": "语气自然"
            }
        ]
    }, ensure_ascii=False)

    scenes = split_scenes_sync(mock_client, "Test input", "modern")
    assert len(scenes) == 1
    assert scenes[0]["title"] == "Scene 1"


def test_split_scenes_markdown_json():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = '```json\n{"scenes": [{"title": "S1", "text": "T", "shot_type": "近景", "narration": "N", "edit_prompt": "P", "instruction": "I"}]}\n```'

    scenes = split_scenes_sync(mock_client, "input", "ancient")
    assert len(scenes) == 1


def test_split_scenes_invalid_json():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = "This is not JSON at all"

    scenes = split_scenes_sync(mock_client, "Some text", "modern")
    assert len(scenes) == 1
    assert scenes[0]["title"] == "Scene 1"
    assert scenes[0]["text"] == "Some text"


def test_split_scenes_empty_scene_list_falls_back():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = json.dumps({"scenes": []}, ensure_ascii=False)

    scenes = split_scenes_sync(mock_client, "Some text", "modern")
    assert len(scenes) == 1
    assert scenes[0]["title"] == "Scene 1"


def test_split_scenes_incomplete_scene_uses_safe_defaults():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = json.dumps({
        "scenes": [{"title": "Only title"}]
    }, ensure_ascii=False)

    scenes = split_scenes_sync(mock_client, "Some text", "modern")

    assert scenes == [{
        "title": "Only title",
        "text": "Some text",
        "shot_type": "中景",
        "narration": "Some text",
        "edit_prompt": "Some text",
        "instruction": "语气自然",
        "character": None,
    }]


def test_split_scenes_includes_style_scene_split_prompt():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = json.dumps({
        "scenes": [{"title": "Scene 1", "text": "T", "shot_type": "中景", "narration": "N", "edit_prompt": "P", "instruction": "I"}]
    }, ensure_ascii=False)

    split_scenes_sync(mock_client, "Some text", "ancient")

    system_message = mock_client.llm_chat.call_args.args[0][0]["content"]
    assert "请将以下古风文段拆分为 N 个场景" in system_message


@pytest.mark.asyncio
async def test_assemble_video_raises_when_ffmpeg_segment_fails(tmp_path, monkeypatch):
    scene = SimpleNamespace(seq=1)
    (tmp_path / "scene_1.png").write_bytes(b"png")
    (tmp_path / "scene_1.mp3").write_bytes(b"mp3")

    class FailedProcess:
        returncode = 1

        async def wait(self):
            return self.returncode

    async def fake_create_subprocess_exec(*args, **kwargs):
        return FailedProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        await assemble_video(tmp_path, [scene], tmp_path / "final.mp4")


@pytest.mark.asyncio
async def test_run_pipeline_task_cleans_partial_outputs_on_failure(db_session_factory, tmp_path, monkeypatch):
    class FailingImageClient:
        def __init__(self):
            self.image_calls = 0

        def llm_chat(self, messages):
            return json.dumps({
                "scenes": [{
                    "title": "Scene 1",
                    "text": "Scene text",
                    "shot_type": "中景",
                    "narration": "Narration",
                    "edit_prompt": "Prompt",
                    "instruction": "语气自然",
                }]
            }, ensure_ascii=False)

        def image_generate(self, **kwargs):
            self.image_calls += 1
            if self.image_calls > 1:
                raise RuntimeError("image service failed")
            return b"reference"

        def tts(self, **kwargs):
            return b"audio"

    monkeypatch.setattr("app.services.pipeline.StepFunClient", FailingImageClient)
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)
    monkeypatch.setattr("app.services.pipeline.async_session", db_session_factory)

    async with db_session_factory() as db:
        user = User(email="pipeline-failure@example.com", password_hash="hash")
        db.add(user)
        await db.flush()
        project = Project(
            user_id=user.id,
            title="Pipeline Failure",
            source_text="足够长的文段用于验证 pipeline 失败清理。",
            style_writing="modern",
            style_visual="ink_wash",
            style_audio="ancient_male",
            status="running",
        )
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, user_id=user.id, status="pending", step="queued", progress=0)
        db.add(task)
        await db.commit()
        task_id = task.id
        project_id = project.id
        user_id = user.id

    project_dir = tmp_path / str(user_id) / str(project_id)

    await run_pipeline_task(task_id)

    async with db_session_factory() as db:
        task = await db.get(Task, task_id)
        project = await db.get(Project, project_id)
        assets = (await db.execute(select(Asset).where(Asset.project_id == project_id))).scalars().all()
        scenes = (await db.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()

    assert task.status == "failed"
    assert task.error_msg == "image service failed"
    assert project.status == "failed"
    assert assets == []
    assert scenes == []
    assert not project_dir.exists()
