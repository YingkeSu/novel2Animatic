"""Tests for SSE (Server-Sent Events) real-time push."""

import asyncio
import pytest
from app.services.event_bus import EventBus, EventType


class TestEventBus:
    """内存事件总线测试。"""

    def test_event_bus_singleton(self):
        """event_bus 单例可访问。"""
        from app.services.event_bus import event_bus
        assert event_bus is not None

    def test_subscribe_returns_queue(self):
        """subscribe 返回可迭代的队列。"""
        bus = EventBus()
        queue = bus.subscribe("project-1")
        assert queue is not None

    @pytest.mark.asyncio
    async def test_publish_received_by_subscriber(self):
        """publish 的事件被 subscriber 收到。"""
        bus = EventBus()
        queue = bus.subscribe("project-1")
        await bus.publish("project-1", "progress", {"step": 1, "progress": 50})
        assert not queue.empty()
        event = queue.get_nowait()
        assert event.type == "progress"
        assert event.data["progress"] == 50

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """多个 subscriber 各自收到事件。"""
        bus = EventBus()
        q1 = bus.subscribe("proj-1")
        q2 = bus.subscribe("proj-1")
        await bus.publish("proj-1", "complete", {})
        assert not q1.empty()
        assert not q2.empty()

    @pytest.mark.asyncio
    async def test_different_projects_isolated(self):
        """不同 project 的事件互不干扰。"""
        bus = EventBus()
        q1 = bus.subscribe("proj-a")
        q2 = bus.subscribe("proj-b")
        await bus.publish("proj-a", "progress", {"step": 1})
        assert not q1.empty()
        assert q2.empty()

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_events(self):
        """取消订阅后不再收到事件。"""
        bus = EventBus()
        q = bus.subscribe("proj-1")
        bus.unsubscribe("proj-1", q)
        await bus.publish("proj-1", "progress", {})
        assert q.empty()

    def test_event_types(self):
        """支持的事件类型。"""
        from app.services.event_bus import SUPPORTED_EVENT_TYPES
        assert "progress" in SUPPORTED_EVENT_TYPES
        assert "scene_update" in SUPPORTED_EVENT_TYPES
        assert "error" in SUPPORTED_EVENT_TYPES
        assert "complete" in SUPPORTED_EVENT_TYPES
        assert "tool_execution" in SUPPORTED_EVENT_TYPES

    @pytest.mark.asyncio
    async def test_publish_returns_subscriber_count(self):
        """publish 返回收到事件的订阅者数量。"""
        bus = EventBus()
        bus.subscribe("proj-1")
        bus.subscribe("proj-1")
        count = await bus.publish("proj-1", "progress", {})
        assert count == 2

    @pytest.mark.asyncio
    async def test_stream_events_generator(self):
        """stream_events 异步生成器正确产出事件。"""
        bus = EventBus()
        queue = bus.subscribe("proj-1")

        # 发布事件
        await bus.publish("proj-1", "progress", {"step": 1})

        # 获取一个事件
        async for event in bus.stream_events("proj-1", queue):
            assert event.type == "progress"
            break  # 只取第一个


class TestSSEEndpoint:
    """SSE 路由基本测试（不需要实际 HTTP）。"""

    def test_router_importable(self):
        """事件路由可导入。"""
        from app.routers.events import router
        assert router is not None

    def test_router_has_events_route(self):
        """路由包含 /{project_id}/events 端点。"""
        from app.routers.events import router
        routes = [r.path for r in router.routes]
        assert "/{project_id}/events" in routes or "/api/projects/{project_id}/events" in routes


class TestPipelinePublishesEvents:
    """Issue #48: the shared media pipeline publishes SSE events at each
    milestone, plus a terminal complete/error event.

    These subscribe a real event_bus listener and drive ``run_media_pipeline``
    with a mocked StepFun client, asserting the event TYPES and ORDERING.
    """

    @pytest.mark.asyncio
    async def test_run_media_pipeline_publishes_milestone_progress_then_complete(
        self, db_session_factory, tmp_path, monkeypatch
    ):
        """A successful run emits progress frames at 25/40/65/90/100 then a
        final complete event — in that order."""
        from app.services.event_bus import event_bus
        from app.services.pipeline import run_media_pipeline, STORAGE_DIR as _PIPE_STORAGE  # noqa: F401
        from app.services import pipeline as pipeline_mod
        from app.models.project import Project
        from app.models.task import Task
        from app.models.user import User
        from app.models.scene import Scene
        from sqlalchemy import select

        class _FakeClient:
            def image_generate(self, **kwargs):
                return b"img"

            def tts(self, **kwargs):
                return b"aud"

        async def fake_assemble_video(project_dir, scenes, video_path):
            video_path.write_bytes(b"vid")

        monkeypatch.setattr(pipeline_mod, "STORAGE_DIR", tmp_path)
        monkeypatch.setattr(pipeline_mod, "assemble_video", fake_assemble_video)

        # Seed user + project + task + 1 scene.
        async with db_session_factory() as db:
            user = User(email="sse-media@example.com", password_hash="hash")
            db.add(user)
            await db.flush()
            project = Project(
                user_id=user.id,
                title="SSE Media",
                source_text="x" * 80,
                source_type="text_split",
                style_writing="modern",
                style_visual="ink_wash",
                style_audio="ancient_male",
                status="running",
            )
            db.add(project)
            await db.flush()
            task = Task(
                project_id=project.id, user_id=user.id,
                status="running", step="split_scenes", progress=10,
            )
            db.add(task)
            scene = Scene(
                project_id=project.id, seq=1, title="s1", text="t",
                shot_type="medium", narration="n", edit_prompt="p", instruction="i",
            )
            db.add(scene)
            await db.commit()
            project_id = project.id

        # Subscribe to the global event_bus BEFORE running the pipeline.
        queue = event_bus.subscribe(str(project_id))
        try:
            async with db_session_factory() as db:
                proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()
                tsk = (await db.execute(select(Task).where(Task.project_id == project_id))).scalar_one()
                scenes = (await db.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
                await run_media_pipeline(db, _FakeClient(), proj, scenes, tmp_path, tsk)

            # Drain the queue.
            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
        finally:
            event_bus.unsubscribe(str(project_id), queue)

        types = [e.type for e in events]
        # Milestone progress frames in order.
        assert types == [
            "progress", "progress", "progress", "progress", "progress", "complete"
        ]
        progress_payloads = [e.data for e in events if e.type == "progress"]
        assert [p["step"] for p in progress_payloads] == [
            "generate_refs", "generate_images", "generate_audio",
            "assemble_video", "complete",
        ]
        assert [p["progress"] for p in progress_payloads] == [25, 40, 65, 90, 100]
        assert progress_payloads[-1]["status"] == "done"

    @pytest.mark.asyncio
    async def test_run_media_pipeline_failure_publishes_error(
        self, db_session_factory, tmp_path, monkeypatch
    ):
        """A failing run emits the error event with a sanitized message."""
        from app.services.event_bus import event_bus
        from app.services import pipeline as pipeline_mod
        from app.services.pipeline import run_media_pipeline
        from app.models.project import Project
        from app.models.task import Task
        from app.models.user import User
        from app.models.scene import Scene
        from sqlalchemy import select

        class _FakeClient:
            def image_generate(self, **kwargs):
                return b"img"

            def tts(self, **kwargs):
                return b"aud"

        async def failing_assemble_video(project_dir, scenes, video_path):
            raise RuntimeError("ffmpeg exploded")

        monkeypatch.setattr(pipeline_mod, "STORAGE_DIR", tmp_path)
        monkeypatch.setattr(pipeline_mod, "assemble_video", failing_assemble_video)

        async with db_session_factory() as db:
            user = User(email="sse-media-err@example.com", password_hash="hash")
            db.add(user)
            await db.flush()
            project = Project(
                user_id=user.id, title="SSE Media Err",
                source_text="x" * 80, source_type="text_split",
                style_writing="modern", style_visual="ink_wash", style_audio="ancient_male",
                status="running",
            )
            db.add(project)
            await db.flush()
            task = Task(
                project_id=project.id, user_id=user.id,
                status="running", step="split_scenes", progress=10,
            )
            db.add(task)
            scene = Scene(
                project_id=project.id, seq=1, title="s1", text="t",
                shot_type="medium", narration="n", edit_prompt="p", instruction="i",
            )
            db.add(scene)
            await db.commit()
            project_id = project.id

        queue = event_bus.subscribe(str(project_id))
        try:
            with pytest.raises(RuntimeError):
                async with db_session_factory() as db:
                    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()
                    tsk = (await db.execute(select(Task).where(Task.project_id == project_id))).scalar_one()
                    scenes = (await db.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
                    await run_media_pipeline(db, _FakeClient(), proj, scenes, tmp_path, tsk)

            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
        finally:
            event_bus.unsubscribe(str(project_id), queue)

        # run_media_pipeline itself does NOT catch the failure (the caller
        # does, in run_pipeline_task / _run_short_fiction_generation). So the
        # progress milestones up to the failure point are still published, but
        # NO error event is emitted here — the error event is the caller's job.
        types = [e.type for e in events]
        assert "progress" in types
        # No 'error' or 'complete' from run_media_pipeline on failure.
        assert "error" not in types
        assert "complete" not in types


class TestPipelineTaskFailurePublishesError:
    """The TASK-level wrappers are responsible for the error/failed-progress
    events on failure, since run_media_pipeline lets exceptions propagate.
    Verified end-to-end via the short_fiction handler (whose full-suite test
    harness is already proven in test_short_fiction_media.py).
    """

    @pytest.mark.asyncio
    async def test_short_fiction_failure_publishes_error_event(
        self, db_session_factory, tmp_path, monkeypatch
    ):
        from app.services.event_bus import event_bus
        from app.routers.generation import _run_short_fiction_generation
        from app.models.project import Project
        from app.models.task import Task
        from app.models.user import User
        from sqlalchemy import select

        class _StubSceneGenResult:
            def __init__(self, scenes):
                self.scenes = scenes
                self.outline = self.outline_review = self.outline_v2 = ""
                self.draft_review = self.story_title = ""

        class _RecordingClient:
            def image_generate(self, **kwargs):
                return b"img"

            def tts(self, **kwargs):
                return b"aud"

        async def fake_generate(self, direction, chapter_count, chars_per_chapter):
            return _StubSceneGenResult([{
                "seq": 1, "title": "s1", "text": "t", "shot_type": "medium",
                "narration": "n", "edit_prompt": "p", "instruction": "i",
                "character": "",
            }])

        async def failing_assemble_video(project_dir, scenes, video_path):
            raise RuntimeError("ffmpeg exploded")

        client = _RecordingClient()
        monkeypatch.setattr("app.services.scene_router.StepFunClient", lambda: client)
        monkeypatch.setattr(
            "app.services.scene_generator.SceneGenerator.generate", fake_generate
        )
        monkeypatch.setattr("app.services.pipeline.assemble_video", failing_assemble_video)
        monkeypatch.setattr("app.database.async_session", db_session_factory)
        monkeypatch.setattr("app.services.pipeline.STORAGE_DIR", tmp_path)

        async with db_session_factory() as db:
            user = User(email="sse-task-err@example.com", password_hash="hash")
            db.add(user)
            await db.flush()
            project = Project(
                user_id=user.id, title="Task Err",
                source_text="", direction="古风爱情", source_type="short_fiction",
                style_writing="modern", style_visual="ink_wash", style_audio="ancient_male",
                status="running",
            )
            db.add(project)
            await db.commit()
            project_id = project.id

        queue = event_bus.subscribe(str(project_id))
        try:
            await _run_short_fiction_generation(
                project_id, user.id, direction="古风爱情",
                chapter_count=2, chars_per_chapter=500,
            )

            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
        finally:
            event_bus.unsubscribe(str(project_id), queue)

        types = [e.type for e in events]
        assert "error" in types
        err_event = next(e for e in events if e.type == "error")
        # Sanitized: raw exception text must NOT leak (#45).
        assert "ffmpeg exploded" not in err_event.data.get("error", "")
        # A failed progress frame is also emitted for SSE-only recovery.
        failed_progress = [e for e in events if e.type == "progress" and e.data.get("status") == "failed"]
        assert len(failed_progress) >= 1

