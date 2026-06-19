"""Tests for AI short fiction scene generator (three-sandwich pipeline)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.scene_generator import SceneGenerator, GenerationResult


class TestSceneGenerator:
    """场景生成器核心测试。"""

    def test_generator_instantiation(self):
        """生成器可实例化。"""
        gen = SceneGenerator()
        assert gen is not None

    def test_generation_result_structure(self):
        """GenerationResult 包含必要字段。"""
        result = GenerationResult(
            scenes=[{"title": "场景1", "text": "内容"}],
            outline="大纲内容",
            outline_review="审纲意见",
            outline_v2="修改后大纲",
            draft_review="审稿意见",
            story_title="故事标题",
        )
        assert len(result.scenes) == 1
        assert result.story_title == "故事标题"

    def test_generation_result_scenes_compatible_with_scene_model(self):
        """生成的场景兼容现有 Scene 模型字段。"""
        result = GenerationResult(
            scenes=[{
                "title": "风雪夜归",
                "text": "腊月二十三，小年夜。",
                "shot_type": "medium",
                "narration": "陆行舟踩着没膝深的雪",
                "edit_prompt": "水墨风格，雪夜山路",
                "instruction": "缓慢推进",
                "character": "陆行舟",
                "source_type": "short_fiction",
            }],
            outline="",
            outline_review="",
            outline_v2="",
            draft_review="",
            story_title="雪夜归人",
        )
        scene = result.scenes[0]
        assert scene["source_type"] == "short_fiction"
        assert "title" in scene
        assert "text" in scene
        assert "shot_type" in scene
        assert "narration" in scene
        assert "edit_prompt" in scene


class TestSceneGeneratorPipeline:
    """三明治 pipeline 流程测试。"""

    @pytest.mark.asyncio
    async def test_generate_calls_agents_in_order(self):
        """generate 调用 6 个 agent 按正确顺序。"""
        gen = SceneGenerator()

        # Mock the LLM calls
        call_order = []

        async def mock_outline(direction, chapter_count, chars_per_chapter):
            call_order.append("outline")
            return "=== SHORT_FICTION_TITLE ===\n测试标题\n=== CHAPTER 1 TITLE ===\n第一章\n=== CHAPTER 1 CONTENT ===\n内容一"

        async def mock_review(text, review_type):
            call_order.append(f"review_{review_type}")
            return "审查意见：整体不错"

        async def mock_revise(original, review, revise_type):
            call_order.append(f"revise_{revise_type}")
            return original  # No changes

        async def mock_write(outline, chapter_count):
            call_order.append("write")
            return "=== SHORT_FICTION_TITLE ===\n测试标题\n=== CHAPTER 1 TITLE ===\n第一章\n=== CHAPTER 1 CONTENT ===\n腊月二十三。"

        async def mock_package(title, outline, draft):
            call_order.append("package")
            return "=== INTRO ===\n简介内容\n=== SELLING_POINTS ===\n卖点1\n卖点2"

        gen._generate_outline = mock_outline
        gen._review_text = mock_review
        gen._revise_text = mock_revise
        gen._write_draft = mock_write
        gen._package = mock_package

        result = await gen.generate(
            direction="古风爱情",
            chapter_count=1,
            chars_per_chapter=100,
        )

        assert "outline" in call_order
        assert "review_outline" in call_order
        assert "revise_outline" in call_order
        assert "write" in call_order
        assert "review_draft" in call_order
        assert "revise_draft" in call_order
        assert "package" in call_order
        assert len(call_order) == 7

    @pytest.mark.asyncio
    async def test_generate_returns_scenes(self):
        """generate 返回包含场景的 GenerationResult。"""
        gen = SceneGenerator()

        async def mock_outline(direction, chapter_count, chars_per_chapter):
            return "=== SHORT_FICTION_TITLE ===\n测试\n=== CHAPTER 1 TITLE ===\n第一章\n=== CHAPTER 1 CONTENT ===\n内容"

        async def mock_review(text, review_type):
            return "OK"

        async def mock_revise(original, review, revise_type):
            return original

        async def mock_write(outline, chapter_count):
            return "=== SHORT_FICTION_TITLE ===\n测试\n=== CHAPTER 1 TITLE ===\n第一章\n=== CHAPTER 1 CONTENT ===\n正文内容。"

        async def mock_package(title, outline, draft):
            return "=== INTRO ===\n简介"

        gen._generate_outline = mock_outline
        gen._review_text = mock_review
        gen._revise_text = mock_revise
        gen._write_draft = mock_write
        gen._package = mock_package

        result = await gen.generate(direction="古风爱情", chapter_count=1)
        assert len(result.scenes) == 1
        assert result.scenes[0]["source_type"] == "short_fiction"

    @pytest.mark.asyncio
    async def test_generate_preserves_first_draft_on_revision_failure(self):
        """修订失败时保留首稿。"""
        gen = SceneGenerator()

        async def mock_outline(direction, chapter_count, chars_per_chapter):
            return "=== SHORT_FICTION_TITLE ===\n测试\n=== CHAPTER 1 TITLE ===\n第一章\n=== CHAPTER 1 CONTENT ===\n内容"

        async def mock_review(text, review_type):
            return "审查意见"

        async def mock_revise(original, review, revise_type):
            if revise_type == "draft":
                raise Exception("修订失败")
            return original

        async def mock_write(outline, chapter_count):
            return "=== SHORT_FICTION_TITLE ===\n测试\n=== CHAPTER 1 TITLE ===\n第一章\n=== CHAPTER 1 CONTENT ===\n正文。"

        async def mock_package(title, outline, draft):
            return "=== INTRO ===\n简介"

        gen._generate_outline = mock_outline
        gen._review_text = mock_review
        gen._revise_text = mock_revise
        gen._write_draft = mock_write
        gen._package = mock_package

        result = await gen.generate(direction="测试", chapter_count=1)
        # Should still have scenes from the first draft
        assert len(result.scenes) == 1
        assert result.draft_review == "审查意见"


class TestSceneGeneratorDefaults:
    """默认参数测试。"""

    def test_default_chapter_count(self):
        """默认章节数为 5。"""
        gen = SceneGenerator()
        assert gen.default_chapter_count == 5

    def test_default_chars_per_chapter(self):
        """默认每章 500 字。"""
        gen = SceneGenerator()
        assert gen.default_chars_per_chapter == 500
