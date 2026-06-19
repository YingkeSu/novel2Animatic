"""Model resolver — maps pipeline steps to specific model configurations.

Implements a priority chain: step override > global config > hardcoded fallback.
Inspired by InkOS's service-resolver.ts architecture.

Usage:
    resolver = ModelResolver()
    model = resolver.resolve("scene_split")
    # model.model_id, model.base_url, model.api_key, model.temperature, ...
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ResolvedModel:
    """Resolved model configuration for a pipeline step."""
    service_name: str
    model_id: str
    base_url: str
    api_key: str
    api_format: str = "openai_chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True


# ── Hardcoded defaults per step ──────────────────────────────────────

_STEP_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "scene_split": {
        "model_id": "step-3.7-flash",
        "temperature": 0.7,
        "max_tokens": 4096,
        "overridable": True,  # LLM step — global config can override model_id
    },
    "image_gen": {
        "model_id": "step-image-edit-2",
        "temperature": 0.7,
        "max_tokens": 1024,
        "overridable": False,  # Specialized model — protected from global override
    },
    "tts": {
        "model_id": "stepaudio-2.5-tts",
        "temperature": 0.7,
        "max_tokens": 4096,
        "overridable": False,
    },
    "outline_review": {
        "model_id": "step-3.7-flash",
        "temperature": 0.3,
        "max_tokens": 2048,
        "overridable": True,
    },
    "draft_review": {
        "model_id": "step-3.7-flash",
        "temperature": 0.3,
        "max_tokens": 2048,
        "overridable": True,
    },
    "outline_revise": {
        "model_id": "step-3.7-flash",
        "temperature": 0.45,
        "max_tokens": 4096,
        "overridable": True,
    },
    "draft_revise": {
        "model_id": "step-3.7-flash",
        "temperature": 0.45,
        "max_tokens": 8192,
        "overridable": True,
    },
    "scene_render": {
        "model_id": "step-3.7-flash",
        "temperature": 0.45,
        "max_tokens": 4096,
        "overridable": True,
    },
    "action_interpret": {
        "model_id": "step-3.7-flash",
        "temperature": 0.15,
        "max_tokens": 1024,
        "overridable": True,
    },
    "world_mutate": {
        "model_id": "step-3.7-flash",
        "temperature": 0.25,
        "max_tokens": 4096,
        "overridable": True,
    },
}

# Global fallback
_DEFAULT_SERVICE = "StepFun"
_DEFAULT_BASE_URL = "https://api.stepfun.com/v1"
_DEFAULT_API_KEY_ENV = "STEPFUN_API_KEY"
_DEFAULT_API_FORMAT = "openai_chat"


class ModelResolver:
    """Resolves model configuration for a given pipeline step.

    Priority: step_overrides[step] > _STEP_DEFAULTS[step] > global_config > hardcoded fallback.

    Design: step defaults protect step-specific model IDs (e.g. image_gen → step-image-edit-2)
    from being overridden by global config. Global config only provides provider-level
    settings (service name, api key, base url) for LLM steps.
    """

    def __init__(
        self,
        global_config: Optional[Dict[str, Any]] = None,
        step_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self._global = global_config or {}
        self._step_overrides = step_overrides or {}

    def resolve(self, step: str) -> ResolvedModel:
        """Resolve model config for a pipeline step.

        Args:
            step: Pipeline step name (e.g., "scene_split", "image_gen").

        Returns:
            ResolvedModel with all fields populated.
        """
        import os

        # Step 1: Start with step-specific defaults (protects model_id for known steps)
        step_default = _STEP_DEFAULTS.get(step, _STEP_DEFAULTS["scene_split"])

        # Step 2: Base config — use step defaults for model-specific fields,
        #         global config for provider-level fields
        is_overridable = step_default.get("overridable", True)
        config = {
            "service_name": self._global.get("service", _DEFAULT_SERVICE),
            "model_id": self._global.get("model_id", step_default["model_id"]) if is_overridable else step_default["model_id"],
            "base_url": self._global.get("base_url", _DEFAULT_BASE_URL),
            "api_key": self._global.get("api_key", os.getenv(_DEFAULT_API_KEY_ENV, "")),
            "api_format": self._global.get("api_format", _DEFAULT_API_FORMAT),
            "temperature": self._global.get("temperature", step_default["temperature"]) if is_overridable else step_default["temperature"],
            "max_tokens": self._global.get("max_tokens", step_default["max_tokens"]) if is_overridable else step_default["max_tokens"],
        }

        # Step 3: Apply step override (highest priority — overrides everything)
        override = self._step_overrides.get(step, {})
        if override:
            config["service_name"] = override.get("service", config["service_name"])
            config["model_id"] = override.get("model_id", config["model_id"])
            config["base_url"] = override.get("base_url", config["base_url"])
            config["api_key"] = override.get("api_key", config["api_key"])
            config["api_format"] = override.get("api_format", config["api_format"])
            config["temperature"] = override.get("temperature", config["temperature"])
            config["max_tokens"] = override.get("max_tokens", config["max_tokens"])

        return ResolvedModel(**config)
