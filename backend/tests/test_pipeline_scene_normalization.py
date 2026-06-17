"""Tests for scene normalization in pipeline prompt parsing."""

from unittest.mock import MagicMock

import pytest

from app.services.pipeline import split_scenes_sync


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {"scenes": {"title": 1}},
            [{
                "title": "Scene 1",
                "text": "Some text",
                "shot_type": "中景",
                "narration": "Some text",
                "edit_prompt": "Some text",
                "instruction": "语气自然",
                "character": None,
            }],
        ),
        (
            {"scenes": [1, 2, 3]},
            [{
                "title": "Scene 1",
                "text": "Some text",
                "shot_type": "中景",
                "narration": "Some text",
                "edit_prompt": "Some text",
                "instruction": "语气自然",
                "character": None,
            }],
        ),
        (
            {"scenes": [{"title": "Scene 1"}, None]},
            [{
                "title": "Scene 1",
                "text": "Some text",
                "shot_type": "中景",
                "narration": "Some text",
                "edit_prompt": "Some text",
                "instruction": "语气自然",
                "character": None,
            }],
        ),
        (
            {"scenes": [{
                "title": "Scene 1",
                "text": "   ",
                "shot_type": "  ",
                "narration": "\n",
                "edit_prompt": " \t ",
                "instruction": "   ",
            }]},
            [{
                "title": "Scene 1",
                "text": "Some text",
                "shot_type": "中景",
                "narration": "Some text",
                "edit_prompt": "Some text",
                "instruction": "语气自然",
                "character": None,
            }],
        ),
    ],
)
def test_split_scenes_normalizes_invalid_scene_shapes(payload, expected):
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = __import__("json").dumps(payload, ensure_ascii=False)

    scenes = split_scenes_sync(mock_client, "Some text", "modern")

    assert scenes == expected


def test_split_scenes_keeps_valid_scene_entries():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = __import__("json").dumps(
        {
            "scenes": [
                {
                    "title": "Valid scene",
                    "text": "Scene body",
                    "shot_type": "远景",
                    "narration": "Narration",
                    "edit_prompt": "Prompt",
                    "instruction": "语气平稳",
                    "character": "主角",
                },
                42,
            ]
        },
        ensure_ascii=False,
    )

    scenes = split_scenes_sync(mock_client, "Some text", "modern")

    assert scenes == [{
        "title": "Valid scene",
        "text": "Scene body",
        "shot_type": "远景",
        "narration": "Narration",
        "edit_prompt": "Prompt",
        "instruction": "语气平稳",
        "character": "主角",
    }]


def test_split_scenes_trims_valid_scene_strings():
    mock_client = MagicMock()
    mock_client.llm_chat.return_value = __import__("json").dumps(
        {
            "scenes": [
                {
                    "title": "  Valid scene  ",
                    "text": "  Scene body  ",
                    "shot_type": "  远景  ",
                    "narration": "  Narration  ",
                    "edit_prompt": "  Prompt  ",
                    "instruction": "  语气平稳  ",
                    "character": "  主角  ",
                },
            ]
        },
        ensure_ascii=False,
    )

    scenes = split_scenes_sync(mock_client, "Some text", "modern")

    assert scenes == [{
        "title": "Valid scene",
        "text": "Scene body",
        "shot_type": "远景",
        "narration": "Narration",
        "edit_prompt": "Prompt",
        "instruction": "语气平稳",
        "character": "主角",
    }]
