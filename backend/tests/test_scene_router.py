"""Tests for scene source routing (text_split / short_fiction / play_world)."""

import pytest
from app.services.scene_router import route_scenes, SceneSource


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
        assert result.handler == "pipeline.split_scenes"

    def test_route_short_fiction(self):
        """short_fiction 来源返回正确的路由信息。"""
        result = route_scenes("short_fiction")
        assert result.source == SceneSource.SHORT_FICTION
        assert result.handler == "scene_generator.generate"

    def test_route_play_world(self):
        """play_world 来源返回正确的路由信息。"""
        result = route_scenes("play_world")
        assert result.source == SceneSource.PLAY_WORLD
        assert result.handler == "world_engine.step"

    def test_route_unknown_source_raises(self):
        """未知来源类型抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unknown source"):
            route_scenes("unknown_source")
