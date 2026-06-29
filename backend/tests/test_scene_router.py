"""Tests for scene source routing (text_split / short_fiction / play_world).

Covers both the legacy ``route_scenes`` metadata API and the real dispatch
entrypoints (``get_generation_kind`` / ``start_background_generation`` /
``run_play_turn``) that the routers now delegate to.
"""

import asyncio

import pytest

from app.services import scene_router
from app.services.scene_router import (
    SceneSource,
    get_generation_kind,
    route_scenes,
    run_play_turn,
    start_background_generation,
)


class TestSceneRouter:
    """场景来源路由测试。"""

    def test_route_scenes_returns_scene_source(self):
        """route_scenes 返回 SceneSource 枚举。"""
        assert SceneSource.TEXT_SPLIT == "text_split"
        assert SceneSource.SHORT_FICTION == "short_fiction"
        assert SceneSource.PLAY_WORLD == "play_world"

    def test_text_split_source_type(self):
        """text_split 来源类型正确。"""
        assert SceneSource.TEXT_SPLIT.value == "text_split"

    def test_short_fiction_source_type(self):
        """short_fiction 来源类型正确。"""
        assert SceneSource.SHORT_FICTION.value == "short_fiction"

    def test_play_world_source_type(self):
        """play_world 来源类型正确。"""
        assert SceneSource.PLAY_WORLD.value == "play_world"

    def test_route_text_split(self):
        """text_split 来源返回正确的路由信息。"""
        result = route_scenes("text_split")
        assert result.source == SceneSource.TEXT_SPLIT
        assert result.handler == "pipeline.run_pipeline_task"

    def test_route_short_fiction(self):
        """short_fiction 来源返回正确的路由信息。"""
        result = route_scenes("short_fiction")
        assert result.source == SceneSource.SHORT_FICTION
        assert result.handler == "scene_router._run_short_fiction_generation"

    def test_route_play_world(self):
        """play_world 来源返回正确的路由信息。"""
        result = route_scenes("play_world")
        assert result.source == SceneSource.PLAY_WORLD
        assert result.handler == "world_engine.WorldEngine.step"

    def test_route_unknown_source_raises(self):
        """未知来源类型抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unknown source"):
            route_scenes("unknown_source")


class TestGenerationKind:
    """get_generation_kind maps each source_type to its dispatch model."""

    def test_text_split_is_background(self):
        assert get_generation_kind("text_split") == "background"

    def test_short_fiction_is_background(self):
        assert get_generation_kind("short_fiction") == "background"

    def test_play_world_is_sync(self):
        assert get_generation_kind("play_world") == "sync"

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            get_generation_kind("bogus")


class TestStartBackgroundGeneration:
    """start_background_generation selects the right background handler.

    These tests assert which handler is selected WITHOUT running the pipeline:
    we monkeypatch the candidate handlers to stand-ins and check which one the
    returned coroutine will invoke.
    """

    def test_text_split_dispatches_run_pipeline_task(self, monkeypatch):
        """text_split selects the shared run_pipeline_task handler."""
        called = {}

        async def fake_run_pipeline_task(task_id):
            called["task_id"] = task_id
            return "text_split-handler"

        # The router imports run_pipeline_task lazily from app.tasks.pipeline.
        import app.tasks.pipeline as pipeline_tasks_module
        monkeypatch.setattr(
            pipeline_tasks_module, "run_pipeline_task", fake_run_pipeline_task
        )

        coro = start_background_generation(
            "text_split", task_id=42, project_id=1, user_id=1
        )
        # Must return an awaitable the router schedules via asyncio.create_task.
        assert asyncio.iscoroutine(coro)
        result = asyncio.run(coro)
        assert result == "text_split-handler"
        assert called["task_id"] == 42

    def test_short_fiction_dispatches_short_fiction_handler(self, monkeypatch):
        """short_fiction selects _run_short_fiction_generation."""
        called = {}

        async def fake_handler(project_id, user_id, direction, chapter_count, chars_per_chapter):
            called.update(
                project_id=project_id, user_id=user_id, direction=direction,
                chapter_count=chapter_count, chars_per_chapter=chars_per_chapter,
            )
            return "short_fiction-handler"

        monkeypatch.setattr(
            scene_router, "_run_short_fiction_generation", fake_handler
        )

        coro = start_background_generation(
            "short_fiction",
            project_id=7, user_id=3, direction="古风爱情",
            chapter_count=2, chars_per_chapter=600,
        )
        assert asyncio.iscoroutine(coro)
        result = asyncio.run(coro)
        assert result == "short_fiction-handler"
        assert called == {
            "project_id": 7, "user_id": 3, "direction": "古风爱情",
            "chapter_count": 2, "chars_per_chapter": 600,
        }

    def test_short_fiction_falls_back_to_default_direction(self, monkeypatch):
        """Omitting direction uses the default story direction."""
        captured = {}

        async def fake_handler(project_id, user_id, direction, chapter_count, chars_per_chapter):
            captured["direction"] = direction

        monkeypatch.setattr(
            scene_router, "_run_short_fiction_generation", fake_handler
        )
        coro = start_background_generation(
            "short_fiction", project_id=1, user_id=1
        )
        asyncio.run(coro)
        assert captured["direction"] == "默认故事"

    def test_play_world_is_not_a_background_source(self):
        """play_world must go through the sync path, not background dispatch."""
        with pytest.raises(ValueError, match="not a background source"):
            start_background_generation("play_world", project_id=1, user_id=1)

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            start_background_generation("bogus", project_id=1, user_id=1)

    def test_text_split_requires_task_id(self):
        with pytest.raises(ValueError, match="task_id is required"):
            start_background_generation(
                "text_split", task_id=None, project_id=1, user_id=1
            )


class TestRunPlayTurn:
    """run_play_turn runs a single WorldEngine turn synchronously."""

    def test_returns_turn_payload_and_scene_dict(self, monkeypatch):
        """run_play_turn returns the response keys + a _scene_dict for persistence."""
        from app.services.world_engine import TurnResult

        fake_result = TurnResult(
            scene_text="竹林深处",
            suggested_actions=["走上石桥", "探索竹林"],
            mutation_summary="无变化",
            turn=2,
            action_kind="look",
        )

        async def fake_step(self, *, world_id, turn, raw_input, context):
            return fake_result

        monkeypatch.setattr(
            "app.services.world_engine.WorldEngine.step", fake_step
        )

        payload = asyncio.run(
            run_play_turn(project_id=5, turn=2, raw_input="看看", context="竹林")
        )

        assert payload["scene_text"] == "竹林深处"
        assert payload["suggested_actions"] == ["走上石桥", "探索竹林"]
        assert payload["mutation_summary"] == "无变化"
        assert payload["turn"] == 2
        assert payload["action_kind"] == "look"
        assert "_scene_dict" in payload

    def test_propagates_world_engine_errors(self, monkeypatch):
        """Engine failures propagate so the router can sanitize them (#45)."""

        async def boom(self, **kwargs):
            raise RuntimeError("internal /secret/ leak")

        monkeypatch.setattr("app.services.world_engine.WorldEngine.step", boom)

        with pytest.raises(RuntimeError, match="secret"):
            asyncio.run(
                run_play_turn(project_id=1, turn=1, raw_input="x", context="y")
            )
