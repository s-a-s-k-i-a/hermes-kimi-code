from __future__ import annotations

import argparse
import json

from hermes_kimi_code.cli import handle_cli, setup_cli
from hermes_kimi_code.errors import KimiACPError


def test_setup_cli_registers_doctor_parser():
    parser = argparse.ArgumentParser()

    setup_cli(parser)
    args = parser.parse_args(["doctor", "--json"])

    assert args.kimi_code_command == "doctor"
    assert args.json is True
    assert args.func is handle_cli


def test_doctor_json_success(monkeypatch, capsys):
    monkeypatch.setattr("hermes_kimi_code.cli.load_plugin_config", lambda: object())
    monkeypatch.setattr(
        "hermes_kimi_code.cli.run_probe",
        lambda _config: {
            "agent": "Kimi Code CLI",
            "version": "test",
            "acp_login_handshake": "accepted",
            "oauth_verified": False,
            "delegate_only": True,
        },
    )

    code = handle_cli(argparse.Namespace(kimi_code_command="doctor", json=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["delegate_only"] is True
    assert payload["oauth_verified"] is False


def test_doctor_preserves_login_error_taxonomy(monkeypatch, capsys):
    monkeypatch.setattr("hermes_kimi_code.cli.load_plugin_config", lambda: object())

    def fail(_config):
        raise KimiACPError(
            "authentication_required",
            "Kimi login expired.",
            "Run `kimi login` in an interactive terminal, then retry.",
        )

    monkeypatch.setattr("hermes_kimi_code.cli.run_probe", fail)

    code = handle_cli(argparse.Namespace(kimi_code_command="doctor", json=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["error_type"] == "authentication_required"
    assert "quota" not in payload["error"].lower()
    assert "kimi login" in payload["recovery"]
