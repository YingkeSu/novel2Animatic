"""Tests for the service connection probe (issue #3).

AC: probe returns {success, api_format, stream_support, models[]}.

All outbound HTTP is mocked — no real network calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from app.services import probe


def _mock_openai_client(models_data, *, stream_support=True):
    """Build a fake OpenAI-compatible client object."""
    client = MagicMock()
    client.models.list.return_value = SimpleNamespace(
        data=[SimpleNamespace(id=m) for m in models_data]
    )
    if stream_support:
        client.chat.completions.create.return_value = iter(["chunk"])
    else:
        client.chat.completions.create.side_effect = RuntimeError("streaming unsupported")
    return client


@pytest.mark.asyncio
async def test_probe_openai_compatible_success():
    fake = _mock_openai_client(["gpt-4o", "gpt-4o-mini"], stream_support=True)
    with patch.object(probe, "build_client_for_service", return_value=fake):
        result = await probe.probe_service(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            api_format="openai_chat",
        )
    assert result["success"] is True
    assert result["api_format"] == "openai_chat"
    assert result["stream_support"] is True
    assert "gpt-4o" in result["models"]
    assert "gpt-4o-mini" in result["models"]


@pytest.mark.asyncio
async def test_probe_openai_compatible_no_stream():
    fake = _mock_openai_client(["llama3"], stream_support=False)
    with patch.object(probe, "build_client_for_service", return_value=fake):
        result = await probe.probe_service(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            api_format="openai_chat",
        )
    assert result["success"] is True
    assert result["stream_support"] is False
    assert result["models"] == ["llama3"]


@pytest.mark.asyncio
async def test_probe_network_failure_marked_unsuccessful():
    fake = MagicMock()
    fake.models.list.side_effect = Exception("connection refused")
    with patch.object(probe, "build_client_for_service", return_value=fake):
        result = await probe.probe_service(
            base_url="https://unreachable.example.com/v1",
            api_key="sk",
            api_format="openai_chat",
        )
    assert result["success"] is False
    assert result["models"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_probe_anthropic_format_does_not_crash():
    # Anthropic format uses a different listing surface; probe must degrade
    # gracefully and report a result shape without crashing.
    result = await probe.probe_service(
        base_url="https://api.anthropic.com/v1",
        api_key="sk-ant",
        api_format="anthropic",
    )
    assert "success" in result
    assert "api_format" in result
    assert "stream_support" in result
    assert "models" in result


@pytest.mark.asyncio
async def test_rest_probe_endpoint(client):
    headers_res = await client.post("/api/auth/register", json={
        "email": "probe-test@example.com", "password": "password123",
    })
    if headers_res.status_code == 409:
        headers_res = await client.post("/api/auth/login", json={
            "email": "probe-test@example.com", "password": "password123",
        })
    headers = {"Authorization": f"Bearer {headers_res.json()['access_token']}"}

    res = await client.post("/api/services", headers=headers, json={
        "name": "Probe Target", "group": "custom",
        "base_url": "https://api.example.com/v1", "api_key": "sk-probe",
        "api_format": "openai_chat",
    })
    svc_id = res.json()["id"]

    fake = _mock_openai_client(["gpt-4o"], stream_support=True)
    with patch.object(probe, "build_client_for_service", return_value=fake):
        res = await client.post(f"/api/services/{svc_id}/probe", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert "gpt-4o" in body["models"]
    assert body["api_format"] == "openai_chat"
    assert "stream_support" in body
