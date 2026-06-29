"""Model service registry with preset configurations.

Provides preset definitions for common LLM providers (StepFun, OpenAI,
Anthropic, DeepSeek) and utilities to build Service configurations.

Inspired by InkOS's service-presets.ts architecture.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services import crypto


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


# Convenience: every preset id (computed once, after _PRESETS is defined).
PRESET_IDS: List[str] = [p.id for p in _PRESETS]

VALID_GROUPS = {"overseas", "china", "aggregator", "custom"}
VALID_API_FORMATS = {"openai_chat", "openai_responses", "anthropic"}


# ── CRUD over the Service table ─────────────────────────────────────
# These wrap the Service model with encryption + JSON (de)serialization so
# callers never handle the api_key_encrypted / *_json columns directly.

async def create_service(
    db: AsyncSession,
    *,
    name: str,
    group: str,
    base_url: str,
    api_key: str,
    api_format: str = "openai_chat",
    stream: bool = True,
    models: Optional[Sequence[str]] = None,
    config: Optional[Dict[str, Any]] = None,
    is_preset: bool = False,
) -> Service:
    """Create and persist a Service row.

    The API key is encrypted at rest via Fernet before being written to
    ``api_key_encrypted``.
    """
    if group not in VALID_GROUPS:
        raise ValueError(f"invalid group: {group}")
    if api_format not in VALID_API_FORMATS:
        raise ValueError(f"invalid api_format: {api_format}")

    svc = Service(
        name=name,
        group=group,
        base_url=base_url,
        api_key_encrypted=crypto.encrypt_api_key(api_key),
        api_format=api_format,
        stream=stream,
        models_json=json.dumps(list(models) if models is not None else []),
        config_json=json.dumps(config or {}),
        is_preset=is_preset,
    )
    db.add(svc)
    await db.commit()
    await db.refresh(svc)
    return svc


async def create_service_from_preset(
    db: AsyncSession,
    preset: ServicePreset,
    api_key: str,
    models: Optional[Sequence[str]] = None,
) -> Service:
    """Persist a Service row built from a preset definition."""
    return await create_service(
        db,
        name=preset.name,
        group=preset.group,
        base_url=preset.base_url,
        api_key=api_key,
        api_format=preset.api_format,
        stream=True,
        models=models if models is not None else preset.models,
        is_preset=True,
    )


async def list_services(db: AsyncSession) -> List[Service]:
    """Return all services, newest first."""
    result = await db.execute(select(Service).order_by(Service.created_at.desc(), Service.id.desc()))
    return list(result.scalars().all())


async def get_service(db: AsyncSession, service_id: int) -> Optional[Service]:
    result = await db.execute(select(Service).where(Service.id == service_id))
    return result.scalar_one_or_none()


async def delete_service(db: AsyncSession, service_id: int) -> bool:
    svc = await get_service(db, service_id)
    if svc is None:
        return False
    await db.delete(svc)
    await db.commit()
    return True


async def get_decrypted_api_key(svc: Service) -> str:
    """Decrypt a Service's stored API key (use only at call time)."""
    return crypto.decrypt_api_key(svc.api_key_encrypted)


def service_to_dict(svc: Service) -> Dict[str, Any]:
    """Serialize a Service for API responses.

    Never includes the encrypted blob or the decrypted key — only a masked
    representation of the key.
    """
    models = json.loads(svc.models_json) if svc.models_json else []
    config = json.loads(svc.config_json) if svc.config_json else {}
    try:
        decrypted = crypto.decrypt_api_key(svc.api_key_encrypted)
    except ValueError:
        decrypted = ""
    return {
        "id": svc.id,
        "name": svc.name,
        "group": svc.group,
        "base_url": svc.base_url,
        "api_key": crypto.mask_key(decrypted),
        "api_key_masked": crypto.mask_key(decrypted),
        "api_format": svc.api_format,
        "stream": svc.stream,
        "models": models,
        "config": config,
        "is_preset": svc.is_preset,
        "probed_at": svc.probed_at.isoformat() if svc.probed_at else None,
        "created_at": svc.created_at.isoformat() if svc.created_at else None,
    }


async def list_services_as_dicts(db: AsyncSession) -> List[Dict[str, Any]]:
    """Return all services as masked dicts (safe for GET responses)."""
    services = await list_services(db)
    return [service_to_dict(s) for s in services]
