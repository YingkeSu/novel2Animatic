"""Tests for secure environment-backed configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_require_secret_and_stepfun_keys(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()
