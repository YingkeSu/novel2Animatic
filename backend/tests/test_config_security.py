"""Tests for secure environment-backed configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_require_secret_and_stepfun_keys(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("value", ["0", "-1"])
def test_settings_reject_non_positive_token_expiry(monkeypatch, value):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("STEPFUN_API_KEY", "test-stepfun")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", value)

    with pytest.raises(ValidationError):
        Settings()
