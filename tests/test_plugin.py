from __future__ import annotations

import asyncio
import importlib.metadata
import json
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
