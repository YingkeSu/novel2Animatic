"""Tests for style engine."""

import pytest
from app.services.style_engine import (
    load_style, get_writing_prompt, get_visual_suffix,
    get_audio_params, list_styles
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
