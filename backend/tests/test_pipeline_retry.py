"""Tests for pipeline auto-retry on transient failures."""

import asyncio
import json
import threading
from types import SimpleNamespace
import pytest
from unittest.mock import MagicMock

from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services.pipeline import run_pipeline_task, _retry_call


# ── Unit tests for _retry_call helper ──────────────────────────────

def test_retry_call_succeeds_on_first_try():
    """_retry_call should return result when fn succeeds."""
    fn = MagicMock(return_value="ok")
    result = _retry_call(fn, max_retries=3, base_delay=0.01)
    assert result == "ok"
    assert fn.call_count == 1


def retry_call_raises_on_non_transient_error():
    """_retry_call should NOT retry non-transient errors (e.g. ValueError)."""
    fn = MagicMock(side_effect=ValueError("bad input"))
    with pytest.raises(ValueError, match="bad input"):
        _retry_call(fn, max_retries=3, base_delay=0.01)
    assert fn.call_count == 1


def test_retry_call_retries_on_timeout():
    """_retry_call should retry on TimeoutError."""
    import openai

    fn = MagicMock()
    fn.side_effect = [
        openai.APITimeoutError(request=MagicMock()),
        openai.APITimeoutError(request=MagicMock()),
        "success",
    ]
    result = _retry_call(fn, max_retries=3, base_delay=0.01)
    assert result == "success"
    assert fn.call_count == 3


def test_retry_call_retries_on_rate_limit():
    """_retry_call should retry on RateLimitError."""
    import openai

    fn = MagicMock()
    fn.side_effect = [
        openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        ),
        "success",
    ]
    result = _retry_call(fn, max_retries=3, base_delay=0.01)
    assert result == "success"
    assert fn.call_count == 2


def test_retry_call_exhausts_retries():
    """_retry_call should raise after max_retries exhausted."""
    import openai

    fn = MagicMock(side_effect=openai.APITimeoutError(request=MagicMock()))
    with pytest.raises(openai.APITimeoutError):
        _retry_call(fn, max_retries=2, base_delay=0.01)
    assert fn.call_count == 2


def test_retry_call_retries_on_connection_error():
    """_retry_call should retry on ConnectionError."""
    fn = MagicMock()
    fn.side_effect = [ConnectionError("network down"), "success"]
    result = _retry_call(fn, max_retries=3, base_delay=0.01)
    assert result == "success"
    assert fn.call_count == 2


# ── Integration test: pipeline retries image generation ────────────

@pytest.mark.asyncio
async def test_run_pipeline_task_retries_image_on_timeout(db_session_factory, tmp_path, monkeypatch):
    """Pipeline should retry image generation on timeout, then succeed."""
    import openai

    class FlakyImageClient:
        def __init__(self):
            self.image_calls = 0

        def llm_chat(self, messages):
            return json.dumps({
                "scenes": [{"title": "Scene 1", "text": "Scene text",
                            "shot_type": "中景", "narration": "Narration",
                            "edit_prompt": "Prompt", "instruction": "语气自然"}]
            }, ensure_ascii=False)

        def image_generate(self, **kwargs):
            self.image_calls += 1
            if self.image_calls == 1:
                raise openai.APITimeoutError(request=MagicMock())
            return b"image"

        def tts(self, **kwargs):
            return b"audio"

    async def fake_assemble_video(project_dir, scenes, video_path):
        video_path.write_bytes(b"video")

    monkeypatch.setattr("app.services.pipeline.StepFunClient", FlakyImageClient)
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)
    monkeypatch.setattr("app.services.pipeline.async_session", db_session_factory)
    monkeypatch.setattr("app.services.pipeline.assemble_video", fake_assemble_video)

    async with db_session_factory() as db:
        user = User(email="retry-test@example.com", password_hash="hash")
        db.add(user)
        await db.flush()
        project = Project(user_id=user.id, title="Retry Test",
                          source_text="足够长的文段用于验证自动重试机制。" * 3,
                          style_writing="modern", style_visual="ink_wash",
                          style_audio="ancient_male", status="running")
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, user_id=user.id,
                    status="pending", step="queued", progress=0)
        db.add(task)
        await db.commit()
        task_id = task.id

    await run_pipeline_task(task_id)

    async with db_session_factory() as db:
        task = await db.get(Task, task_id)

    assert task.status == "done"
    assert task.progress == 100


@pytest.mark.asyncio
async def test_run_pipeline_task_fails_after_max_retries(db_session_factory, tmp_path, monkeypatch):
    """Pipeline should fail after exhausting retries."""
    import openai

    class AlwaysTimeoutClient:
        def llm_chat(self, messages):
            return json.dumps({
                "scenes": [{"title": "Scene 1", "text": "Scene text",
                            "shot_type": "中景", "narration": "Narration",
                            "edit_prompt": "Prompt", "instruction": "语气自然"}]
            }, ensure_ascii=False)

        def image_generate(self, **kwargs):
            raise openai.APITimeoutError(request=MagicMock())

        def tts(self, **kwargs):
            return b"audio"

    monkeypatch.setattr("app.services.pipeline.StepFunClient", AlwaysTimeoutClient)
    monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)
    monkeypatch.setattr("app.services.pipeline.async_session", db_session_factory)

    async with db_session_factory() as db:
        user = User(email="retry-exhaust@example.com", password_hash="hash")
        db.add(user)
        await db.flush()
        project = Project(user_id=user.id, title="Retry Exhaust",
                          source_text="足够长的文段用于验证重试耗尽后失败。" * 3,
                          style_writing="modern", style_visual="ink_wash",
                          style_audio="ancient_male", status="running")
        db.add(project)
        await db.flush()
        task = Task(project_id=project.id, user_id=user.id,
                    status="pending", step="queued", progress=0)
        db.add(task)
        await db.commit()
        task_id = task.id

    await run_pipeline_task(task_id)

    async with db_session_factory() as db:
        task = await db.get(Task, task_id)

    assert task.status == "failed"
    # error_msg is sanitized: generic message, no raw timeout/exception details.
    assert task.error_msg == "生成失败，请稍后重试。"
    assert "timed out" not in (task.error_msg or "").lower()
    assert "TimeoutError" not in (task.error_msg or "")
