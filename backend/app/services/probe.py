"""Service connection probe.

Returns a uniform result shape::

    {success, api_format, stream_support, models[], error?}

For OpenAI-compatible services (``openai_chat`` / ``openai_responses``) we
use the OpenAI SDK's ``models.list()`` to enumerate models and a streaming
chat request to detect stream support. For ``anthropic`` we degrade
gracefully (no live listing) — the probe still reports a result shape and
a best-guess stream_support, without crashing.

All network IO goes through :func:`build_client_for_service`, which is the
single seam tests patch to mock outbound HTTP. No probe call ever hits the
network in the test suite.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = 15  # seconds — keep probes snappy


def build_client_for_service(base_url: str, api_key: str, api_format: str):
    """Construct an OpenAI-SDK-compatible client for probing.

    This is the only place that performs real network IO in this module.
    Tests patch this function to inject a fake client.
    """
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url, timeout=_PROBE_TIMEOUT)


async def probe_service(
    *,
    base_url: str,
    api_key: str,
    api_format: str,
) -> Dict[str, Any]:
    """Probe a service endpoint and report a uniform result.

    Returns a dict with keys: success, api_format, stream_support, models,
    and (on failure) error.
    """
    result: Dict[str, Any] = {
        "success": False,
        "api_format": api_format,
        "stream_support": False,
        "models": [],
    }

    if api_format == "anthropic":
        # Anthropic's /v1/messages surface has no OpenAI-style models.list();
        # skip live probing and report a best-guess shape.
        result["success"] = True
        result["stream_support"] = True
        result["models"] = []
        return result

    try:
        client = build_client_for_service(base_url, api_key, api_format)
        models = _list_openai_models(client)
        result["models"] = models
        result["stream_support"] = _detect_stream_support(client, models, api_format)
        result["success"] = True
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        logger.warning("Service probe failed for %s: %s", base_url, exc)
        result["error"] = str(exc)
        result["success"] = False
        result["models"] = []
        result["stream_support"] = False

    return result


def _list_openai_models(client) -> List[str]:
    page = client.models.list()
    # OpenAI SDK returns objects with .data[i].id
    data = getattr(page, "data", None)
    if data is None and isinstance(page, list):  # tolerate plain lists
        data = page
    models: List[str] = []
    for item in data or []:
        model_id = getattr(item, "id", None)
        if model_id:
            models.append(str(model_id))
    return sorted(set(models))


def _detect_stream_support(client, models: List[str], api_format: str) -> bool:
    """Best-effort stream support check via a streaming chat request.

    We only fire the request when there is at least one model to target;
    otherwise we conservatively report False.
    """
    if not models:
        return False
    target = models[0]
    try:
        stream = client.chat.completions.create(
            model=target,
            messages=[{"role": "user", "content": "ping"}],
            stream=True,
            max_tokens=1,
        )
        # Consume at least one chunk to confirm streaming actually works.
        for _ in stream:
            break
        return True
    except Exception:  # noqa: BLE001 — stream detection is best-effort
        return False
