"""Tests for pipeline scene splitting (with mocked LLM)."""

import pytest
import json
from unittest.mock import MagicMock
from app.services.pipeline import split_scenes_sync


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
