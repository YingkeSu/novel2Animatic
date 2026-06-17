"""Tests for Pydantic v2-compatible model configuration."""

import importlib
import sys
import warnings


def test_backend_models_import_without_pydantic_config_deprecation():
    for module_name in ("app.config", "app.schemas"):
        sys.modules.pop(module_name, None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("app.config")
        importlib.import_module("app.schemas")

    deprecated_config_warnings = [
        warning for warning in caught
        if "Support for class-based `config` is deprecated" in str(warning.message)
    ]
    assert deprecated_config_warnings == []
