"""Tests for style engine."""

import pytest
from app.services.style_engine import (
    load_style, get_writing_prompt, get_scene_split_prompt, get_visual_suffix,
    get_audio_params, list_styles, select_scene_split_system_prompt,
    build_scene_split_system_prompt
)


def test_load_writing_style():
    style = load_style("writing", "ancient")
    assert "system_prompt" in style
    assert "古风" in style["name"]


def test_load_visual_style():
    style = load_style("visual", "ink_wash")
    assert "prompt_suffix" in style
    assert "水墨" in style["name"]


def test_load_audio_style():
    style = load_style("audio", "ancient_male")
    assert "voice" in style
    assert style["voice"] == "cixingnansheng"


def test_load_nonexistent_style():
    style = load_style("writing", "nonexistent")
    assert style == {}


def test_load_style_rejects_path_traversal(tmp_path, monkeypatch):
    styles_dir = tmp_path / "styles"
    (styles_dir / "writing").mkdir(parents=True)
    (tmp_path / "escape.yaml").write_text("name: escaped\nsecret: true\n", encoding="utf-8")
    monkeypatch.setattr("app.services.style_engine.STYLES_DIR", styles_dir)

    style = load_style("writing", "../../escape")

    assert style == {}


def test_get_writing_prompt():
    prompt = get_writing_prompt("modern")
    assert len(prompt) > 0
    assert "现代" in prompt or "白话" in prompt


def test_get_scene_split_prompt():
    prompt = get_scene_split_prompt("ancient")
    assert "古风文段拆分为 N 个场景" in prompt


def test_build_scene_split_system_prompt_prefers_scene_split_prompt():
    prompt = build_scene_split_system_prompt("ancient")
    assert "古风文段拆分为 N 个场景" in prompt
    assert "请用古风文笔改写以下内容" not in prompt


def test_select_scene_split_system_prompt_prefers_scene_split_prompt():
    prompt = select_scene_split_system_prompt("scene split", "system prompt")

    assert prompt == "scene split"


def test_select_scene_split_system_prompt_falls_back_when_scene_split_prompt_is_blank():
    assert select_scene_split_system_prompt(None, "system prompt") == "system prompt"
    assert select_scene_split_system_prompt("", "system prompt") == "system prompt"
    assert select_scene_split_system_prompt("   ", "system prompt") == "system prompt"


def test_select_scene_split_system_prompt_uses_default_when_prompts_are_blank():
    assert select_scene_split_system_prompt(None, None) == "你是一位专业的编剧。"
    assert select_scene_split_system_prompt("", "") == "你是一位专业的编剧。"
    assert select_scene_split_system_prompt("   ", "   ") == "你是一位专业的编剧。"


def test_build_scene_split_system_prompt_falls_back_to_writing_prompt(tmp_path, monkeypatch):
    styles_dir = tmp_path / "styles"
    writing_dir = styles_dir / "writing"
    writing_dir.mkdir(parents=True)
    (writing_dir / "plain.yaml").write_text(
        "name: plain\nsystem_prompt: |\n  fallback writing prompt\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.style_engine.STYLES_DIR", styles_dir)

    prompt = build_scene_split_system_prompt("plain")

    assert prompt == "fallback writing prompt"


def test_build_scene_split_system_prompt_ignores_whitespace_scene_split_prompt(tmp_path, monkeypatch):
    styles_dir = tmp_path / "styles"
    writing_dir = styles_dir / "writing"
    writing_dir.mkdir(parents=True)
    (writing_dir / "plain.yaml").write_text(
        'name: plain\nscene_split_prompt: "   "\nsystem_prompt: fallback writing prompt\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("app.services.style_engine.STYLES_DIR", styles_dir)

    prompt = build_scene_split_system_prompt("plain")

    assert prompt == "fallback writing prompt"


def test_build_scene_split_system_prompt_uses_default_for_unknown_style():
    prompt = build_scene_split_system_prompt("does_not_exist")

    assert prompt == "你是一位专业的编剧。"


def test_get_visual_suffix():
    suffix = get_visual_suffix("ink_wash")
    assert "水墨" in suffix


def test_get_audio_params():
    params = get_audio_params("ancient_male")
    assert params["voice"] == "cixingnansheng"
    assert "instruction" in params
    assert "speed" in params


def test_list_writing_styles():
    styles = list_styles("writing")
    names = [s["name"] for s in styles]
    assert "modern" in names
    assert "ancient" in names
    assert "wuxia" in names
    assert "xuanhuan" in names


def test_list_visual_styles():
    styles = list_styles("visual")
    names = [s["name"] for s in styles]
    assert "ink_wash" in names
    assert "anime" in names


def test_list_audio_styles():
    styles = list_styles("audio")
    names = [s["name"] for s in styles]
    assert "ancient_male" in names
    assert "modern_female" in names
