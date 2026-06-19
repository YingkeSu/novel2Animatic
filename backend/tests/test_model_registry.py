"""Tests for model service registry and preset system."""

import pytest
from app.services.model_registry import (
    get_preset_services,
    get_service_presets_by_group,
    build_service_from_preset,
    ServicePreset,
)


class TestServicePresets:
    """预设服务定义测试。"""

    def test_preset_services_exist(self):
        """预设服务列表非空。"""
        presets = get_preset_services()
        assert len(presets) > 0

    def test_stepfun_preset_exists(self):
        """StepFun 预设存在。"""
        presets = get_preset_services()
        stepfun = [p for p in presets if p.id == "stepfun"]
        assert len(stepfun) == 1
        assert stepfun[0].name == "StepFun"
        assert stepfun[0].group == "china"

    def test_openai_preset_exists(self):
        """OpenAI 预设存在。"""
        presets = get_preset_services()
        openai = [p for p in presets if p.id == "openai"]
        assert len(openai) == 1
        assert openai[0].group == "overseas"

    def test_deepseek_preset_exists(self):
        """DeepSeek 预设存在。"""
        presets = get_preset_services()
        deepseek = [p for p in presets if p.id == "deepseek"]
        assert len(deepseek) == 1
        assert deepseek[0].group == "china"

    def test_anthropic_preset_exists(self):
        """Anthropic 预设存在。"""
        presets = get_preset_services()
        anthropic = [p for p in presets if p.id == "anthropic"]
        assert len(anthropic) == 1
        assert anthropic[0].group == "overseas"

    def test_preset_has_required_fields(self):
        """每个预设都有必要字段。"""
        for preset in get_preset_services():
            assert preset.id, f"Preset missing id"
            assert preset.name, f"Preset {preset.id} missing name"
            assert preset.group in ("overseas", "china", "aggregator", "custom"), \
                f"Preset {preset.id} has invalid group: {preset.group}"
            assert preset.base_url, f"Preset {preset.id} missing base_url"
            assert preset.api_format in ("openai_chat", "openai_responses", "anthropic"), \
                f"Preset {preset.id} has invalid api_format: {preset.api_format}"
            assert len(preset.models) > 0, f"Preset {preset.id} has no models"

    def test_filter_by_group(self):
        """按分组过滤预设。"""
        china = get_service_presets_by_group("china")
        assert all(p.group == "china" for p in china)
        assert len(china) >= 2  # StepFun + DeepSeek

        overseas = get_service_presets_by_group("overseas")
        assert all(p.group == "overseas" for p in overseas)
        assert len(overseas) >= 2  # OpenAI + Anthropic

    def test_build_service_from_preset(self):
        """从预设构建服务配置。"""
        preset = get_service_presets_by_group("china")[0]
        service = build_service_from_preset(preset, api_key="test-key")
        assert service.name == preset.name
        assert service.base_url == preset.base_url
        assert service.api_key == "test-key"
        assert service.api_format == preset.api_format


class TestServicePresetData:
    """预设数据完整性测试。"""

    def test_stepfun_default_models(self):
        """StepFun 默认模型包含 step-3.7-flash。"""
        presets = get_preset_services()
        stepfun = next(p for p in presets if p.id == "stepfun")
        assert "step-3.7-flash" in stepfun.models

    def test_openai_default_models(self):
        """OpenAI 默认模型包含 gpt-4o。"""
        presets = get_preset_services()
        openai = next(p for p in presets if p.id == "openai")
        assert "gpt-4o" in openai.models

    def test_deepseek_default_models(self):
        """DeepSeek 默认模型包含 deepseek-chat。"""
        presets = get_preset_services()
        deepseek = next(p for p in presets if p.id == "deepseek")
        assert "deepseek-chat" in deepseek.models

    def test_stepfun_base_url(self):
        """StepFun base_url 正确。"""
        presets = get_preset_services()
        stepfun = next(p for p in presets if p.id == "stepfun")
        assert "stepfun.com" in stepfun.base_url

    def test_preset_temperature_defaults(self):
        """预设有合理的默认温度。"""
        for preset in get_service_presets_by_group("china"):
            if preset.default_temperature is not None:
                assert 0 <= preset.default_temperature <= 2
