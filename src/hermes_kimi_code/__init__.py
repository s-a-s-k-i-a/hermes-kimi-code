"""Standalone, delegate-only Kimi Code ACP plugin for Hermes Agent."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .acp import run_delegation
from .cli import handle_cli, setup_cli
from .config import SUPPORTED_MODELS, command_is_available, load_plugin_config
from .errors import KimiACPError

__version__ = "0.1.0"

KIMI_CODE_DELEGATE_SCHEMA = {
    "name": "kimi_code_delegate",
    "description": (
        "Ask the locally authenticated Kimi Code CLI for read-only advisory analysis. "
        "Use only when explicit Kimi delegation is useful. This is not a primary, fallback, "
        "or auxiliary model route, and it cannot perform filesystem, terminal, permission, "
        "or other side effects."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100_000,
                "description": "Self-contained task or question to delegate to Kimi Code.",
            },
            "model": {
                "type": "string",
                "enum": ["k3", "k3-256k"],
                "description": "Optional Kimi model; defaults to plugin config.",
            },
            "thinking": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
                "pattern": "^[a-z0-9][a-z0-9_-]*$",
                "description": (
                    "Optional reasoning effort. Auto uses the ACP session current value; "
                    "otherwise the exact option id must be offered by Kimi."
                ),
            },
        },
    },
}


def _error_payload(exc: KimiACPError) -> str:
    return json.dumps(
        {
            "ok": False,
            "error_type": exc.error_type,
            "error": exc.message,
            "recovery": exc.recovery,
            "delegate_only": True,
            "hermes_model_changed": False,
            "approval_requests_forwarded": False,
        },
        ensure_ascii=False,
    )


def _handle_delegate_sync(args: dict[str, Any]) -> str:
    try:
        if not isinstance(args, dict):
            raise KimiACPError("input", "Tool arguments must be an object.")
        config = load_plugin_config()
        model = str(args.get("model") or config.model).strip()
        thinking = str(args.get("thinking") or config.thinking).strip().lower()
        if model not in SUPPORTED_MODELS:
            raise KimiACPError("input", "model must be k3 or k3-256k.")
        result = run_delegation(
            config,
            str(args.get("prompt") or ""),
            model=model,
            thinking=thinking,
        )
        return json.dumps(
            {
                "ok": True,
                **result,
                "delegate_only": True,
                "hermes_model_changed": False,
                "approval_requests_forwarded": False,
            },
            ensure_ascii=False,
        )
    except KimiACPError as exc:
        return _error_payload(exc)


async def handle_kimi_code_delegate(args: dict[str, Any], **_kwargs: Any) -> str:
    """Keep blocking subprocess I/O off Hermes gateway event loops."""

    return await asyncio.to_thread(_handle_delegate_sync, args)


def register(ctx: Any) -> None:
    """Register one explicit delegate tool and one diagnostic CLI command."""

    ctx.register_tool(
        name="kimi_code_delegate",
        toolset="kimi_code_delegate",
        schema=KIMI_CODE_DELEGATE_SCHEMA,
        handler=handle_kimi_code_delegate,
        check_fn=command_is_available,
        is_async=True,
        description=KIMI_CODE_DELEGATE_SCHEMA["description"],
        emoji="🌙",
    )
    ctx.register_cli_command(
        name="kimi-code",
        help="Kimi Code delegate diagnostics",
        setup_fn=setup_cli,
        handler_fn=handle_cli,
        description="Check the standalone, delegate-only Kimi Code ACP integration.",
    )


__all__ = [
    "KIMI_CODE_DELEGATE_SCHEMA",
    "handle_kimi_code_delegate",
    "register",
]
