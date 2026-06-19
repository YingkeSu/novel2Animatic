"""Model service registry with preset configurations.

Provides preset definitions for common LLM providers (StepFun, OpenAI,
Anthropic, DeepSeek) and utilities to build Service configurations.

Inspired by InkOS's service-presets.ts architecture.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ServicePreset:
    """Definition of a preset service provider."""
    id: str
    name: str
    group: str  # overseas, china, aggregator, custom
    base_url: str
    api_format: str  # openai_chat, openai_responses, anthropic
    models: List[str] = field(default_factory=list)
    default_temperature: Optional[float] = 0.7
    description: str = ""


@dataclass
class ServiceConfig:
    """Runtime service configuration (built from preset or custom)."""
    name: str
    base_url: str
    api_key: str
    api_format: str
    stream: bool = True
    models: List[str] = field(default_factory=list)
    default_temperature: Optional[float] = 0.7


# ── Preset definitions ──────────────────────────────────────────────

_PRESETS: List[ServicePreset] = [
    # ── China ──
    ServicePreset(
        id="stepfun",
        name="StepFun",
        group="china",
        base_url="https://api.stepfun.com/v1",
        api_format="openai_chat",
        models=["step-3.7-flash", "step-2-16k", "step-1-32k"],
        default_temperature=0.7,
        description="阶跃星辰 (StepFun) 大模型 API",
    ),
    ServicePreset(
        id="deepseek",
        name="DeepSeek",
        group="china",
        base_url="https://api.deepseek.com/v1",
        api_format="openai_chat",
        models=["deepseek-chat", "deepseek-reasoner"],
        default_temperature=0.7,
        description="DeepSeek 大模型 API",
    ),
    ServicePreset(
        id="moonshot",
        name="Moonshot",
        group="china",
        base_url="https://api.moonshot.cn/v1",
        api_format="openai_chat",
        models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        default_temperature=0.7,
        description="月之暗面 (Moonshot) 大模型 API",
    ),
    ServicePreset(
        id="zhipu",
        name="Zhipu",
        group="china",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_format="openai_chat",
        models=["glm-4-flash", "glm-4-plus"],
        default_temperature=0.7,
        description="智谱 (Zhipu/GLM) 大模型 API",
    ),

    # ── Overseas ──
    ServicePreset(
        id="openai",
        name="OpenAI",
        group="overseas",
        base_url="https://api.openai.com/v1",
        api_format="openai_chat",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        default_temperature=0.7,
        description="OpenAI GPT 系列模型",
    ),
    ServicePreset(
        id="anthropic",
        name="Anthropic",
        group="overseas",
        base_url="https://api.anthropic.com/v1",
        api_format="anthropic",
        models=["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
        default_temperature=0.7,
        description="Anthropic Claude 系列模型",
    ),
    ServicePreset(
        id="google",
        name="Google",
        group="overseas",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_format="openai_chat",
        models=["gemini-2.0-flash", "gemini-1.5-pro"],
        default_temperature=0.7,
        description="Google Gemini 系列模型",
    ),
]


def get_preset_services() -> List[ServicePreset]:
    """Return all preset service definitions."""
    return list(_PRESETS)


def get_service_presets_by_group(group: str) -> List[ServicePreset]:
    """Return presets filtered by group name."""
    return [p for p in _PRESETS if p.group == group]


def get_preset_by_id(preset_id: str) -> Optional[ServicePreset]:
    """Look up a preset by its id."""
    for p in _PRESETS:
        if p.id == preset_id:
            return p
    return None


def build_service_from_preset(
    preset: ServicePreset,
    api_key: str,
    models: Optional[List[str]] = None,
) -> ServiceConfig:
    """Build a runtime ServiceConfig from a preset definition.

    Args:
        preset: The preset to build from.
        api_key: API key for the service.
        models: Override models list (uses preset defaults if None).

    Returns:
        ServiceConfig ready for use by model resolver.
    """
    return ServiceConfig(
        name=preset.name,
        base_url=preset.base_url,
        api_key=api_key,
        api_format=preset.api_format,
        stream=True,
        models=models or list(preset.models),
        default_temperature=preset.default_temperature,
    )
