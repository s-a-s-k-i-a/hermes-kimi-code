from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from hermes_kimi_code import handle_kimi_code_delegate, register
from hermes_kimi_code.errors import KimiACPError


class RecordingContext:
    def __init__(self):
        self.tools = []
        self.commands = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_cli_command(self, **kwargs):
        self.commands.append(kwargs)


def test_register_exposes_only_delegate_tool_and_diagnostic_cli():
    context = RecordingContext()

    register(context)

    assert [tool["name"] for tool in context.tools] == ["kimi_code_delegate"]
    assert context.tools[0]["is_async"] is True
    assert "primary" in context.tools[0]["schema"]["description"]
    assert [command["name"] for command in context.commands] == ["kimi-code"]


def test_pip_entrypoint_loads_a_module_with_register():
    entrypoint = next(
        entrypoint
        for entrypoint in importlib.metadata.entry_points().select(group="hermes_agent.plugins")
        if entrypoint.name == "kimi-code-delegate"
    )

    loaded = entrypoint.load()

    assert loaded.__name__ == "hermes_kimi_code"
    assert loaded.register is register


def test_git_plugin_root_loader_exposes_register_without_code_duplication():
    root = Path(__file__).resolve().parents[1]
    module_name = "kimi_code_delegate_git_plugin"
    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        assert module.register.__name__ == "register"
        assert module.register.__module__.endswith("src.hermes_kimi_code")
    finally:
        for loaded_name in list(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
                sys.modules.pop(loaded_name, None)


def test_handler_returns_structured_success(monkeypatch):
    config = SimpleNamespace(model="k3", thinking="auto")
    monkeypatch.setattr("hermes_kimi_code.load_plugin_config", lambda: config)
    monkeypatch.setattr(
        "hermes_kimi_code.run_delegation",
        lambda *_args, **_kwargs: {
            "response": "answer",
            "model": "kimi-code/k3",
            "thinking": "high",
        },
    )

    result = asyncio.run(handle_kimi_code_delegate({"prompt": "hello"}))

    assert json.loads(result) == {
        "ok": True,
        "response": "answer",
        "model": "kimi-code/k3",
        "thinking": "high",
        "delegate_only": True,
        "hermes_model_changed": False,
        "approval_requests_forwarded": False,
    }


def test_handler_returns_structured_input_error(monkeypatch):
    result = asyncio.run(handle_kimi_code_delegate({"prompt": "hello", "model": "bad"}))
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["error_type"] in {"input", "cli_not_found"}
    assert payload["hermes_model_changed"] is False
    assert payload["approval_requests_forwarded"] is False


def test_handler_rejects_non_string_and_unknown_arguments_before_config(monkeypatch):
    monkeypatch.setattr(
        "hermes_kimi_code.load_plugin_config",
        lambda: (_ for _ in ()).throw(AssertionError("config must not load")),
    )

    for arguments in (
        {"prompt": {"not": "text"}},
        {"prompt": "hello", "model": 3},
        {"prompt": "hello", "thinking": ["high"]},
        {"prompt": "hello", "surprise": True},
    ):
        payload = json.loads(asyncio.run(handle_kimi_code_delegate(arguments)))
        assert payload["ok"] is False
        assert payload["error_type"] == "input"


def test_handler_contains_unexpected_internal_errors(monkeypatch):
    config = SimpleNamespace(model="k3", thinking="auto")
    monkeypatch.setattr("hermes_kimi_code.load_plugin_config", lambda: config)
    monkeypatch.setattr(
        "hermes_kimi_code.run_delegation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private detail")),
    )

    payload = json.loads(asyncio.run(handle_kimi_code_delegate({"prompt": "hello"})))

    assert payload["error_type"] == "internal"
    assert "private detail" not in payload["error"]


def test_empty_provider_turn_is_actionable_without_claiming_quota(monkeypatch):
    config = SimpleNamespace(model="k3", thinking="auto")
    agent = SimpleNamespace(model="current-primary", provider="current-provider")
    monkeypatch.setattr("hermes_kimi_code.load_plugin_config", lambda: config)

    def fail_without_provider_detail(*_args, **_kwargs):
        raise KimiACPError(
            "empty_response",
            "Kimi ACP returned no text. The provider status is unknown.",
            "Check Kimi login and account quota in an interactive terminal, then retry.",
        )

    monkeypatch.setattr("hermes_kimi_code.run_delegation", fail_without_provider_detail)

    result = asyncio.run(handle_kimi_code_delegate({"prompt": "hello"}, agent=agent))
    payload = json.loads(result)

    assert payload == {
        "ok": False,
        "error_type": "empty_response",
        "error": "Kimi ACP returned no text. The provider status is unknown.",
        "recovery": "Check Kimi login and account quota in an interactive terminal, then retry.",
        "delegate_only": True,
        "hermes_model_changed": False,
        "approval_requests_forwarded": False,
    }
    assert (agent.model, agent.provider) == ("current-primary", "current-provider")
