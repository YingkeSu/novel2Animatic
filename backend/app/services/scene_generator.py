"""AI short fiction scene generator — three-sandwich pipeline.

Implements a 6-stage pipeline inspired by InkOS Short:
  1. Generate outline
  2. Review outline
  3. Revise outline
  4. Write draft (all chapters at once)
  5. Review draft
  6. Revise draft → final scenes

Each stage uses the TAG parser for structured output extraction.
Revision failures preserve the first draft (never overwrite a good draft with a bad revision).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.text_parser import parse_tag_blocks

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of a short fiction generation pipeline run."""
    scenes: List[Dict[str, Any]]
    outline: str
    outline_review: str
    outline_v2: str
    draft_review: str
    story_title: str
    sales_package: Optional[str] = None


class SceneGenerator:
    """Short fiction scene generator with three-sandwich quality control.

    Usage:
        gen = SceneGenerator()
        result = await gen.generate(direction="古风爱情", chapter_count=5)
        # result.scenes — list of Scene-compatible dicts
    """

    def __init__(
        self,
        llm_fn=None,
        default_chapter_count: int = 5,
        default_chars_per_chapter: int = 500,
    ) -> None:
        self.llm_fn = llm_fn
        self.default_chapter_count = default_chapter_count
        self.default_chars_per_chapter = default_chars_per_chapter

    async def generate(
        self,
        direction: str,
        chapter_count: Optional[int] = None,
        chars_per_chapter: Optional[int] = None,
    ) -> GenerationResult:
        """Run the full 6-stage generation pipeline.

        Args:
            direction: Creative direction (genre, style, theme).
            chapter_count: Number of chapters (default: self.default_chapter_count).
            chars_per_chapter: Target characters per chapter (default: self.default_chars_per_chapter).

        Returns:
            GenerationResult with scenes, outline, reviews, and story metadata.
        """
        chapters = chapter_count or self.default_chapter_count
        chars = chars_per_chapter or self.default_chars_per_chapter

        # Stage 1: Generate outline
        logger.info("Stage 1: Generating outline for %d chapters", chapters)
        outline_v1 = await self._generate_outline(direction, chapters, chars)

        # Stage 2: Review outline
        logger.info("Stage 2: Reviewing outline")
        outline_review = await self._review_text(outline_v1, "outline")

        # Stage 3: Revise outline (skip if review is empty)
        logger.info("Stage 3: Revising outline")
        if outline_review.strip():
            outline_v2 = await self._revise_text(outline_v1, outline_review, "outline")
        else:
            logger.warning("Outline review empty, skipping revision")
            outline_v2 = outline_v1

        # Stage 4: Write draft
        logger.info("Stage 4: Writing draft")
        draft_v1 = await self._write_draft(outline_v2, chapters)

        # Stage 5: Review draft
        logger.info("Stage 5: Reviewing draft")
        draft_review = await self._review_text(draft_v1, "draft")

        # Stage 6: Revise draft (skip if review is empty, fallback to first draft on error)
        logger.info("Stage 6: Revising draft")
        if draft_review.strip():
            try:
                draft_v2 = await self._revise_text(draft_v1, draft_review, "draft")
                final_draft = draft_v2
            except Exception as e:
                logger.warning("Draft revision failed, preserving first draft: %s", e)
                final_draft = draft_v1
        else:
            logger.warning("Draft review empty, using first draft")
            final_draft = draft_v1

        # Extract story title and scenes from final draft
        story_title = self._extract_title(outline_v2, final_draft)
        scenes = self._extract_scenes(final_draft, direction)

        # Package (optional)
        sales_package = None
        try:
            sales_package = await self._package(story_title, outline_v2, final_draft)
        except Exception as e:
            logger.warning("Packaging failed: %s", e)

        return GenerationResult(
            scenes=scenes,
            outline=outline_v1,
            outline_review=outline_review,
            outline_v2=outline_v2,
            draft_review=draft_review,
            story_title=story_title,
            sales_package=sales_package,
        )

    async def _call_llm(self, messages, temperature=0.7, **kwargs):
        """Call the LLM function."""
        if not self.llm_fn:
            raise RuntimeError("No llm_fn provided to SceneGenerator")
        return await self.llm_fn(messages, temperature=temperature, **kwargs)

    async def _generate_outline(self, direction: str, chapter_count: int, chars_per_chapter: int) -> str:
        """Stage 1: Generate story outline from creative direction."""
        messages = [
            {"role": "system", "content": "你是一个专业的故事策划。请根据用户的方向创作故事大纲。"},
            {"role": "user", "content": f"请为一个{direction}风格的故事创作大纲，共{chapter_count}章，每章约{chars_per_chapter}字。\n\n请使用以下格式：\n=== SHORT_FICTION_PLAN_TITLE ===\n故事标题\n\n=== CHAPTER 1 TITLE ===\n章节标题\n=== CHAPTER 1 CONTENT ===\n章节内容摘要\n\n以此类推。"},
        ]
        return await self._call_llm(messages, temperature=0.7)

    async def _review_text(self, text: str, review_type: str) -> str:
        """Stage 2/5: Review text (outline or draft)."""
        messages = [
            {"role": "system", "content": "你是一个专业的文学编辑。请审阅文本并给出改进建议。"},
            {"role": "user", "content": f"请审阅以下{review_type}，给出具体的改进建议：\n\n{text}"},
        ]
        return await self._call_llm(messages, temperature=0.3)

    async def _revise_text(self, original: str, review: str, revise_type: str) -> str:
        """Stage 3/6: Revise text based on review feedback."""
        messages = [
            {"role": "system", "content": "你是一个专业的作家。请根据审阅意见修改文本。"},
            {"role": "user", "content": f"原文：\n{original}\n\n审阅意见：\n{review}\n\n请根据意见修改{revise_type}，输出修改后的完整文本。"},
        ]
        return await self._call_llm(messages, temperature=0.5)

    async def _write_draft(self, outline: str, chapter_count: int) -> str:
        """Stage 4: Write the full draft from the outline."""
        messages = [
            {"role": "system", "content": "你是一个专业的作家。请根据大纲写出完整的故事。"},
            {"role": "user", "content": f"请根据以下大纲写出完整故事，共{chapter_count}章。\n\n大纲：\n{outline}\n\n请使用以下格式：\n=== SHORT_FICTION_TITLE ===\n故事标题\n\n=== CHAPTER 1 TITLE ===\n章节标题\n=== CHAPTER 1 CONTENT ===\n章节完整内容\n\n以此类推。"},
        ]
        return await self._call_llm(messages, temperature=0.8)

    async def _package(self, title: str, outline: str, draft: str) -> str:
        """Stage 7: Generate sales package (intro, selling points, cover prompt)."""
        messages = [
            {"role": "system", "content": "你是一个专业的文学营销专家。"},
            {"role": "user", "content": f"请为故事《{title}》生成销售包装，包括：简介、卖点、封面提示词。\n\n大纲：\n{outline}\n\n故事：\n{draft}"},
        ]
        return await self._call_llm(messages, temperature=0.5)

    def _extract_title(self, outline: str, draft: str) -> str:
        """Extract story title from outline or draft."""
        # Try draft first
        blocks = parse_tag_blocks(draft)
        if "SHORT_FICTION_TITLE" in blocks:
            return blocks["SHORT_FICTION_TITLE"].strip()

        # Try outline
        blocks = parse_tag_blocks(outline)
        if "SHORT_FICTION_PLAN_TITLE" in blocks:
            return blocks["SHORT_FICTION_PLAN_TITLE"].strip()
        if "SHORT_FICTION_TITLE" in blocks:
            return blocks["SHORT_FICTION_TITLE"].strip()

        return "未命名故事"

    def _extract_scenes(self, draft: str, direction: str) -> List[Dict[str, Any]]:
        """Extract scenes from draft text using TAG parser.

        Returns a list of Scene-compatible dicts with source_type="short_fiction".
        """
        blocks = parse_tag_blocks(draft)
        scenes = []

        # Find all chapter blocks
        i = 1
        while True:
            title_key = f"CHAPTER {i} TITLE"
            content_key = f"CHAPTER {i} CONTENT"

            if title_key not in blocks and content_key not in blocks:
                break

            title = blocks.get(title_key, f"场景 {i}").strip()
            content = blocks.get(content_key, "").strip()

            if content:  # Only include non-empty chapters
                scenes.append({
                    "title": title,
                    "text": content,
                    "shot_type": "medium",  # Default, will be refined by style engine
                    "narration": content[:200],  # First 200 chars as narration
                    "edit_prompt": f"{direction}风格，{title}",
                    "instruction": "缓慢推进",
                    "character": "",
                    "source_type": "short_fiction",
                    "seq": i,
                })

            i += 1

        return scenes
