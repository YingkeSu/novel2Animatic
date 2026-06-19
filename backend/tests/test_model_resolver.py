"""Tests for model resolver — maps pipeline steps to specific models."""

import pytest
from app.services.model_resolver import ModelResolver, ResolvedModel


class TestModelResolver:
    """模型路由解析器测试。"""

    def test_resolve_returns_resolved_model(self):
        """resolve_model 返回 ResolvedModel 对象。"""
        resolver = ModelResolver()
        result = resolver.resolve("scene_split")
        assert isinstance(result, ResolvedModel)

    def test_default_fallback_to_stepfun(self):
        """未配置时 fallback 到 StepFun step-3.7-flash。"""
        resolver = ModelResolver()
        result = resolver.resolve("scene_split")
        assert result.service_name == "StepFun"
        assert result.model_id == "step-3.7-flash"
        assert "stepfun.com" in result.base_url

    def test_resolve_image_gen_fallback(self):
        """image_gen 步骤 fallback 到 StepFun image model。"""
        resolver = ModelResolver()
        result = resolver.resolve("image_gen")
        assert result.model_id == "step-image-edit-2"

    def test_resolve_tts_fallback(self):
        """tts 步骤 fallback 到 StepFun TTS model。"""
        resolver = ModelResolver()
        result = resolver.resolve("tts")
        assert result.model_id == "stepaudio-2.5-tts"

    def test_resolve_outline_review_fallback(self):
        """outline_review fallback 到 step-3.7-flash (低温度)。"""
        resolver = ModelResolver()
        result = resolver.resolve("outline_review")
        assert result.model_id == "step-3.7-flash"
        assert result.temperature <= 0.3

    def test_resolve_draft_review_fallback(self):
        """draft_review fallback 到 step-3.7-flash (低温度)。"""
        resolver = ModelResolver()
        result = resolver.resolve("draft_review")
        assert result.model_id == "step-3.7-flash"
        assert result.temperature <= 0.3

    def test_resolve_unknown_step_uses_global_default(self):
        """未知步骤使用全局默认配置。"""
        resolver = ModelResolver()
        result = resolver.resolve("unknown_step")
        assert result.model_id == "step-3.7-flash"

    def test_global_override(self):
        """全局配置覆盖默认值。"""
        resolver = ModelResolver(global_config={
            "service": "deepseek",
            "model_id": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "test-key",
        })
        result = resolver.resolve("scene_split")
        assert result.service_name == "deepseek"
        assert result.model_id == "deepseek-chat"

    def test_step_override_takes_priority(self):
        """步骤级覆盖优先于全局配置。"""
        resolver = ModelResolver(
            global_config={
                "service": "deepseek",
                "model_id": "deepseek-chat",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "key-1",
            },
            step_overrides={
                "scene_split": {
                    "service": "openai",
                    "model_id": "gpt-4o",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "key-2",
                },
            },
        )
        result = resolver.resolve("scene_split")
        assert result.model_id == "gpt-4o"

        # Other steps still use global
        result2 = resolver.resolve("image_gen")
        assert result2.model_id == "step-image-edit-2"  # image_gen has its own fallback


class TestResolvedModel:
    """ResolvedModel 数据结构测试。"""

    def test_resolved_model_fields(self):
        """ResolvedModel 包含必要字段。"""
        resolver = ModelResolver()
        result = resolver.resolve("scene_split")
        assert hasattr(result, "service_name")
        assert hasattr(result, "model_id")
        assert hasattr(result, "base_url")
        assert hasattr(result, "api_key")
        assert hasattr(result, "temperature")
        assert hasattr(result, "max_tokens")

    def test_temperature_defaults(self):
        """不同步骤有不同的默认温度。"""
        resolver = ModelResolver()
        split = resolver.resolve("scene_split")
        review = resolver.resolve("outline_review")
        # 审查温度应低于生成
        assert review.temperature <= split.temperature
