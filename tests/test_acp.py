from __future__ import annotations

import concurrent.futures
import os
import time

import pytest

from hermes_kimi_code.acp import run_delegation, run_probe, sanitize_diagnostic
from hermes_kimi_code.config import build_child_environment
from hermes_kimi_code.errors import KimiACPError


def test_probe_checks_identity_and_existing_login(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory())

    result = run_probe(config)

    assert result == {
        "agent": "Kimi Code CLI",
        "version": "test",
        "acp_login_handshake": "accepted",
        "oauth_verified": False,
        "delegate_only": True,
        "prompt_capabilities": {"image": True},
    }


def test_delegation_is_end_to_end_and_denies_side_effects(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory())

    result = run_delegation(config, "Review this text", model="k3", thinking="auto")

    assert result["response"].startswith("safe answer from ")
    assert result["model"] == "kimi-code/k3"
    assert result["thinking"] == "high"
    assert not os.path.exists("/tmp/forbidden")


def test_permission_without_reject_option_is_cancelled(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("permission-no-reject"))

    result = run_delegation(config, "Review this text", model="k3", thinking="auto")

    assert result["response"].startswith("safe answer from ")
    assert not os.path.exists("/tmp/forbidden")


def test_each_parallel_delegation_has_an_isolated_process(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory())

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda prompt: run_delegation(config, prompt, model="k3", thinking="low"),
                ["first", "second"],
            )
        )

    process_ids = {result["response"].rsplit(" ", 1)[-1] for result in results}
    assert len(process_ids) == 2


def test_expired_oauth_is_not_misreported_as_quota(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("auth-error"))

    with pytest.raises(KimiACPError) as captured:
        run_probe(config)

    assert captured.value.error_type == "authentication_required"
    assert "kimi login" in captured.value.recovery
    assert "quota" not in captured.value.message.lower()


def test_unexpected_response_id_fails_protocol(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("wrong-id"))

    with pytest.raises(KimiACPError, match="unexpected request id") as captured:
        run_delegation(config, "hello", model="k3", thinking="auto")

    assert captured.value.error_type == "protocol"


def test_timeout_cancels_and_kills_process(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("timeout"), timeout_seconds=1.0)
    started = time.monotonic()

    with pytest.raises(KimiACPError) as captured:
        run_delegation(config, "hello", model="k3", thinking="auto")

    assert captured.value.error_type == "timeout"
    assert time.monotonic() - started < 5


def test_wrong_acp_identity_fails_capability_gate(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("wrong-agent"))

    with pytest.raises(KimiACPError) as captured:
        run_probe(config)

    assert captured.value.error_type == "capability"


@pytest.mark.parametrize("mode", ["malformed-json", "oversized-line"])
def test_invalid_wire_frames_fail_protocol(fake_kimi_factory, plugin_config_factory, mode):
    config = plugin_config_factory(fake_kimi_factory(mode))

    with pytest.raises(KimiACPError) as captured:
        run_probe(config)

    assert captured.value.error_type == "protocol"


def test_early_exit_redacts_diagnostics_and_points_to_login(
    fake_kimi_factory, plugin_config_factory
):
    config = plugin_config_factory(fake_kimi_factory("early-exit"))

    with pytest.raises(KimiACPError) as captured:
        run_probe(config)

    assert captured.value.error_type == "authentication_required"
    assert "secret-value" not in captured.value.message
    assert "kimi login" in captured.value.recovery


def test_missing_login_capability_fails_closed(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("no-login"))

    with pytest.raises(KimiACPError) as captured:
        run_probe(config)

    assert captured.value.error_type == "capability"


def test_empty_success_is_not_accepted(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("empty"))

    with pytest.raises(KimiACPError) as captured:
        run_delegation(config, "hello", model="k3", thinking="auto")

    assert captured.value.error_type == "empty_response"


def test_child_environment_is_allowlisted(monkeypatch):
    monkeypatch.setenv("HOME", "/safe/home")
    monkeypatch.setenv("PATH", "/safe/bin")
    monkeypatch.setenv("KIMI_CODE_HOME", "/safe/kimi")
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")

    environment = build_child_environment()

    assert environment["HOME"] == "/safe/home"
    assert environment["PATH"] == "/safe/bin"
    assert environment["KIMI_CODE_HOME"] == "/safe/kimi"
    assert "KIMI_ACCESS_TOKEN" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert "TELEGRAM_BOT_TOKEN" not in environment


def test_diagnostics_are_redacted_and_bounded():
    diagnostic = (
        "Bearer top-secret access_token=another-secret "
        "https://user:proxy-secret@example.test " + "x" * 10_000
    )

    cleaned = sanitize_diagnostic(diagnostic)

    assert "top-secret" not in cleaned
    assert "another-secret" not in cleaned
    assert "proxy-secret" not in cleaned
    assert "[REDACTED]" in cleaned
    assert len(cleaned) < 4_200


@pytest.mark.parametrize("prompt", ["", "   "])
def test_empty_prompt_fails_before_inference(fake_kimi_factory, plugin_config_factory, prompt):
    config = plugin_config_factory(fake_kimi_factory())

    with pytest.raises(KimiACPError) as captured:
        run_delegation(config, prompt, model="k3", thinking="auto")

    assert captured.value.error_type == "input"


def test_auto_thinking_requires_server_current_value(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("thinking-no-current"))

    with pytest.raises(KimiACPError) as captured:
        run_delegation(config, "hello", model="k3", thinking="auto")

    assert captured.value.error_type == "capability"
    assert "current thinking value" in captured.value.message


def test_explicit_thinking_must_be_offered(fake_kimi_factory, plugin_config_factory):
    config = plugin_config_factory(fake_kimi_factory("thinking-low-only"))

    with pytest.raises(KimiACPError) as captured:
        run_delegation(config, "hello", model="k3", thinking="high")

    assert captured.value.error_type == "capability"
    assert "does not offer thinking 'high'" in captured.value.message
