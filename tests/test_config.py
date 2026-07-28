from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from hermes_kimi_code.config import load_plugin_config
from hermes_kimi_code.errors import KimiACPError


def _config(command: Path, **entry):
    return {"plugins": {"entries": {"kimi-code-delegate": {"command": str(command), **entry}}}}


def test_operator_config_resolves_command_and_cwd(fake_kimi_factory, tmp_path):
    command = fake_kimi_factory()

    config = load_plugin_config(
        _config(
            command,
            working_directory=str(tmp_path),
            timeout_seconds=42,
            startup_timeout_seconds=4,
            model="k3-256k",
            thinking="high",
        )
    )

    assert config.command == str(command.resolve())
    assert config.working_directory == tmp_path.resolve()
    assert config.timeout_seconds == 42
    assert config.startup_timeout_seconds == 4
    assert config.model == "k3-256k"
    assert config.thinking == "high"


def test_thinking_defaults_to_server_negotiation(fake_kimi_factory):
    config = load_plugin_config(_config(fake_kimi_factory()))

    assert config.thinking == "auto"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("timeout_seconds", 0),
        ("startup_timeout_seconds", 100),
        ("model", "unknown"),
        ("thinking", "bad value"),
        ("working_directory", 123),
    ],
)
def test_invalid_operator_config_fails_closed(fake_kimi_factory, key, value):
    with pytest.raises(KimiACPError) as captured:
        load_plugin_config(_config(fake_kimi_factory(), **{key: value}))

    assert captured.value.error_type == "configuration"


def test_future_thinking_option_is_validated_by_acp_not_static_config(fake_kimi_factory):
    config = load_plugin_config(_config(fake_kimi_factory(), thinking="future-level"))

    assert config.thinking == "future-level"


@pytest.mark.parametrize(
    "config",
    [
        [],
        {"plugins": []},
        {"plugins": {"entries": []}},
        {"plugins": {"entries": {"kimi-code-delegate": "invalid"}}},
    ],
)
def test_malformed_hermes_plugin_structure_fails_closed(config):
    with pytest.raises(KimiACPError) as captured:
        load_plugin_config(config)  # type: ignore[arg-type]

    assert captured.value.error_type == "configuration"


def test_hermes_config_loader_failure_is_not_silently_replaced(monkeypatch):
    fake_config = ModuleType("hermes_cli.config")

    def fail():
        raise RuntimeError("malformed config")

    fake_config.load_config = fail  # type: ignore[attr-defined]
    fake_package = ModuleType("hermes_cli")
    monkeypatch.setitem(sys.modules, "hermes_cli", fake_package)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", fake_config)

    with pytest.raises(KimiACPError) as captured:
        load_plugin_config()

    assert captured.value.error_type == "configuration"
    assert "malformed config" not in captured.value.message
