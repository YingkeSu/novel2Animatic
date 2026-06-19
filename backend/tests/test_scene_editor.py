"""Tests for scene editing and single-scene regeneration."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.services.scene_editor import SceneEditor, EditResult


class TestSceneEditor:
    """场景编辑器测试。"""

    def test_edit_result_structure(self):
        """EditResult 包含必要字段。"""
        result = EditResult(
            scene_seq=1,
            field="text",
            old_value="旧文本",
            new_value="新文本",
            success=True,
        )
        assert result.success is True
        assert result.scene_seq == 1

    def test_regeneration_result_structure(self):
        """重新生成结果。"""
        result = EditResult(
            scene_seq=1,
            field="image",
            old_value="old.png",
            new_value="new.png",
            success=True,
        )
        assert result.field == "image"

    def test_supported_edit_fields(self):
        """支持的编辑字段。"""
        editor = SceneEditor()
        assert "text" in editor.editable_fields
        assert "title" in editor.editable_fields
        assert "narration" in editor.editable_fields
        assert "edit_prompt" in editor.editable_fields
        assert "shot_type" in editor.editable_fields

    def test_unsupported_field_raises(self):
        """不支持的字段抛出 ValueError。"""
        editor = SceneEditor()
        with pytest.raises(ValueError, match="not editable"):
            editor.validate_field("unsupported_field")
