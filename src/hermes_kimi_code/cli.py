"""Hermes CLI diagnostics for the standalone Kimi delegate plugin."""

from __future__ import annotations

import argparse
import json

from .acp import run_probe
from .config import load_plugin_config
from .errors import KimiACPError


def setup_cli(parser: argparse.ArgumentParser) -> None:
    subcommands = parser.add_subparsers(dest="kimi_code_command")
    doctor = subcommands.add_parser(
        "doctor",
        help="Check Kimi CLI, ACP capabilities, and the existing CLI-owned login",
    )
    doctor.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.set_defaults(func=handle_cli)


def handle_cli(args: argparse.Namespace) -> int:
    if getattr(args, "kimi_code_command", None) != "doctor":
        print("usage: hermes kimi-code doctor [--json]")
        return 2
    as_json = bool(getattr(args, "json", False))
    try:
        config = load_plugin_config()
        result = run_probe(config)
        payload = {"ok": True, **result}
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Kimi Code ACP: OK ({payload['agent']} {payload['version']})")
            print("ACP login handshake: accepted")
            print("OAuth: not verified until a real delegated prompt succeeds")
            print("Routing: delegate-only (primary/fallback/auxiliary disabled)")
        return 0
    except KimiACPError as exc:
        payload = {
            "ok": False,
            "error_type": exc.error_type,
            "error": exc.message,
            "recovery": exc.recovery,
        }
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Kimi Code ACP: FAILED [{exc.error_type}]")
            print(exc.message)
            if exc.recovery:
                print(exc.recovery)
        return 1
