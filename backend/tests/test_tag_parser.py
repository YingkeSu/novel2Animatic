"""Tests for === TAG === structured text parser."""

import pytest
from app.services.text_parser import parse_tag_blocks, TagParseError


class TestParseTagBlocks:
    """=== TAG === 格式解析器核心测试。"""

    def test_single_tag_block(self):
        """单个标签块正确提取。"""
        text = """=== TITLE ===
My Story Title"""
        result = parse_tag_blocks(text)
        assert result["TITLE"] == "My Story Title"

    def test_multiple_tag_blocks(self):
        """多个标签块按顺序提取。"""
        text = """=== TITLE ===
My Story

=== CHAPTER 1 TITLE ===
The Beginning

=== CHAPTER 1 CONTENT ===
Once upon a time..."""
        result = parse_tag_blocks(text)
        assert result["TITLE"] == "My Story"
        assert result["CHAPTER 1 TITLE"] == "The Beginning"
        assert result["CHAPTER 1 CONTENT"] == "Once upon a time..."

    def test_multiline_content(self):
        """多行内容正确归入同一标签。"""
        text = """=== CHAPTER 1 CONTENT ===
Line 1
Line 2
Line 3"""
        result = parse_tag_blocks(text)
        assert "Line 1" in result["CHAPTER 1 CONTENT"]
        assert "Line 2" in result["CHAPTER 1 CONTENT"]
        assert "Line 3" in result["CHAPTER 1 CONTENT"]

    def test_empty_content(self):
        """空内容标签返回空字符串。"""
        text = """=== TITLE ===

=== SUBTITLE ===
Real content"""
        result = parse_tag_blocks(text)
        assert result["TITLE"] == ""
        assert result["SUBTITLE"] == "Real content"

    def test_empty_input(self):
        """空输入返回空 dict。"""
        assert parse_tag_blocks("") == {}
        assert parse_tag_blocks("   ") == {}

    def test_no_tags(self):
        """无标签文本返回空 dict。"""
        text = "Just some plain text without any tags."
        assert parse_tag_blocks(text) == {}

    def test_fallback_to_markdown_headers(self):
        """无 === TAG === 时 fallback 到 Markdown ## 标题。"""
        text = """## TITLE
My Story

## CHAPTER 1
The Beginning"""
        result = parse_tag_blocks(text)
        assert result["TITLE"] == "My Story"
        assert result["CHAPTER 1"] == "The Beginning"

    def test_malformed_tag_skipped(self):
        """畸形标签（不完整的 === 标记）被跳过。"""
        text = """=== VALID TAG ===
Good content

=== INCOMPLETE
This should be skipped or handled gracefully

=== ANOTHER VALID ===
More good content"""
        result = parse_tag_blocks(text)
        assert "VALID TAG" in result
        assert "ANOTHER VALID" in result

    def test_whitespace_trimmed(self):
        """标签名和内容的前后空白被修剪。"""
        text = """===   TITLE   ===
  My Story  
"""
        result = parse_tag_blocks(text)
        assert "TITLE" in result
        assert result["TITLE"].strip() == "My Story"

    def test_content_before_first_tag_ignored(self):
        """第一个标签之前的文本被忽略。"""
        text = """Some preamble text here.

=== TITLE ===
My Story"""
        result = parse_tag_blocks(text)
        assert "TITLE" in result
        assert len(result) == 1

    def test_duplicate_tags_last_wins(self):
        """重复标签名时，最后一个内容覆盖前面的。"""
        text = """=== TITLE ===
First Title

=== TITLE ===
Second Title"""
        result = parse_tag_blocks(text)
        assert result["TITLE"] == "Second Title"

    def test_real_short_fiction_output(self):
        """模拟 InkOS 短篇小说的实际输出格式。"""
        text = """=== SHORT_FICTION_TITLE ===
雪夜归人

=== SHORT_FICTION_OPENING_HOOK ===
大雪封山三日，他终于叩响了那扇门。

=== CHAPTER 1 TITLE ===
风雪夜归

=== CHAPTER 1 CONTENT ===
腊月二十三，小年夜。

陆行舟踩着没膝深的雪，一步步往山上走。背篓里的年货压得肩膀生疼，
但他的脚步没有慢下来。

远处的灯火在雪幕中若隐若现。那是他和林婉清的家。

=== CHAPTER 2 TITLE ===
旧事重提

=== CHAPTER 2 CONTENT ===
门开了。

林婉清站在门口，围裙上还沾着面粉。她看见陆行舟，愣了一瞬，
然后转身回了屋。"""
        result = parse_tag_blocks(text)
        assert result["SHORT_FICTION_TITLE"] == "雪夜归人"
        assert "大雪封山三日" in result["SHORT_FICTION_OPENING_HOOK"]
        assert "陆行舟" in result["CHAPTER 1 CONTENT"]
        assert "林婉清" in result["CHAPTER 2 CONTENT"]
        assert len(result) == 6

    def test_case_sensitive_tags(self):
        """标签名大小写敏感。"""
        text = """=== title ===
lower

=== TITLE ===
upper"""
        result = parse_tag_blocks(text)
        assert result["title"] == "lower"
        assert result["TITLE"] == "upper"

    def test_special_characters_in_tag_name(self):
        """标签名支持数字、空格、下划线。"""
        text = """=== CHAPTER 1_TITLE ===
Content"""
        result = parse_tag_blocks(text)
        assert "CHAPTER 1_TITLE" in result
