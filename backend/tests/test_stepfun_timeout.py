"""Tests for StepFunClient timeout configuration."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.stepfun_client import StepFunClient


def test_stepfun_client_passes_timeout_to_openai():
    """StepFunClient should pass timeout to OpenAI client constructor."""
    with patch("app.services.stepfun_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client

        StepFunClient(api_key="test", base_url="https://test.com", timeout=120)

        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs["timeout"] == 120


def test_stepfun_client_default_timeout():
    """StepFunClient should default to 120s timeout."""
    with patch("app.services.stepfun_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client

        StepFunClient(api_key="test", base_url="https://test.com")

        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs["timeout"] == 120


def test_stepfun_client_llm_chat_passes_timeout_kwarg():
    """llm_chat should pass timeout kwarg to chat completion."""
    with patch("app.services.stepfun_client.OpenAI") as MockOpenAI:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="hi"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        MockOpenAI.return_value = mock_client

        client = StepFunClient(api_key="test", base_url="https://test.com")
        client.llm_chat([{"role": "user", "content": "hi"}])

        create_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "timeout" not in create_kwargs  # timeout is on client, not per-call


def test_stepfun_client_image_generate_times_out():
    """image_generate should propagate timeout errors."""
    import openai

    with patch("app.services.stepfun_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        mock_client.images.generate.side_effect = openai.APITimeoutError(
            request=MagicMock()
        )
        MockOpenAI.return_value = mock_client

        client = StepFunClient(api_key="test", base_url="https://test.com")

        with pytest.raises(openai.APITimeoutError):
            client.image_generate(prompt="test")
