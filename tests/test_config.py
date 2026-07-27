from __future__ import annotations

from pathlib import Path

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
