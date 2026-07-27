"""Operator-owned configuration and child-process environment policy."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import KimiACPError

PLUGIN_ID = "kimi-code-delegate"

SUPPORTED_MODELS = {
    "k3": "kimi-code/k3",
    "kimi-code/k3": "kimi-code/k3",
    "k3-256k": "kimi-code/k3-256k",
    "kimi-code/k3-256k": "kimi-code/k3-256k",
}
_INHERITED_ENV = {
    "PATH",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "KIMI_CODE_HOME",
    "KIMI_DISABLE_TELEMETRY",
    "KIMI_CODE_NO_AUTO_UPDATE",
    "KIMI_CLI_NO_AUTO_UPDATE",
    "KIMI_DISABLE_CRON",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
}


@dataclass(frozen=True, slots=True)
class PluginConfig:
    command: str
    working_directory: Path
    timeout_seconds: float = 300.0
    startup_timeout_seconds: float = 10.0
    model: str = "k3"
    thinking: str = "auto"


def _plugin_entry(config: dict[str, Any] | None) -> dict[str, Any]:
    plugins = (config or {}).get("plugins")
    if not isinstance(plugins, dict):
        return {}
    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        return {}
    entry = entries.get(PLUGIN_ID)
    return entry if isinstance(entry, dict) else {}


def _load_hermes_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        loaded = load_config()
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _bounded_float(value: Any, *, name: str, default: float, low: float, high: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise KimiACPError("configuration", f"{name} must be a number, not a boolean.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise KimiACPError("configuration", f"{name} must be a number.") from exc
    if not low <= parsed <= high:
        raise KimiACPError("configuration", f"{name} must be between {low:g} and {high:g} seconds.")
    return parsed


def _resolve_command(raw: Any) -> str:
    if raw is not None and not isinstance(raw, str):
        raise KimiACPError(
            "configuration",
            "plugins.entries.kimi-code-delegate.command must be a string.",
        )
    configured = str(raw or "").strip()
    if configured:
        expanded = str(Path(configured).expanduser())
        if os.sep in expanded or (os.altsep and os.altsep in expanded):
            candidate = Path(expanded)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
            raise KimiACPError(
                "cli_not_found",
                "The configured Kimi Code executable does not exist or is not executable.",
                "Set plugins.entries.kimi-code-delegate.command to the Kimi executable path.",
            )
        found = shutil.which(expanded)
        if found:
            return str(Path(found).resolve())
        raise KimiACPError(
            "cli_not_found",
            f"The configured Kimi Code command '{expanded}' is not available on PATH.",
            "Install Kimi Code or set plugins.entries.kimi-code-delegate.command.",
        )

    home_candidate = Path.home() / ".kimi-code" / "bin" / "kimi"
    if home_candidate.is_file() and os.access(home_candidate, os.X_OK):
        return str(home_candidate.resolve())
    found = shutil.which("kimi")
    if found:
        return str(Path(found).resolve())
    raise KimiACPError(
        "cli_not_found",
        "Kimi Code CLI was not found.",
        "Install Kimi Code, or configure plugins.entries.kimi-code-delegate.command.",
    )


def load_plugin_config(config: dict[str, Any] | None = None) -> PluginConfig:
    """Load and validate only the operator-owned plugin configuration."""

    entry = _plugin_entry(_load_hermes_config() if config is None else config)
    command = _resolve_command(entry.get("command"))

    raw_cwd = entry.get("working_directory")
    if raw_cwd is not None and not isinstance(raw_cwd, str):
        raise KimiACPError(
            "configuration",
            "plugins.entries.kimi-code-delegate.working_directory must be a string.",
        )
    cwd = Path(str(raw_cwd or os.getcwd())).expanduser().resolve()
    if not cwd.is_dir():
        raise KimiACPError(
            "configuration", "The configured Kimi working directory is not a directory."
        )

    model = str(entry.get("model") or "k3").strip()
    if model not in SUPPORTED_MODELS:
        raise KimiACPError(
            "configuration",
            "Configured Kimi model is not supported; use k3 or k3-256k.",
        )
    raw_thinking = entry.get("thinking", "auto")
    if not isinstance(raw_thinking, str):
        raise KimiACPError("configuration", "Configured Kimi thinking must be a string.")
    thinking = raw_thinking.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", thinking):
        raise KimiACPError(
            "configuration",
            "Configured Kimi thinking must be auto or a valid ACP option id.",
        )

    return PluginConfig(
        command=command,
        working_directory=cwd,
        timeout_seconds=_bounded_float(
            entry.get("timeout_seconds"),
            name="timeout_seconds",
            default=300.0,
            low=1.0,
            high=1800.0,
        ),
        startup_timeout_seconds=_bounded_float(
            entry.get("startup_timeout_seconds"),
            name="startup_timeout_seconds",
            default=10.0,
            low=1.0,
            high=60.0,
        ),
        model=model,
        thinking=thinking,
    )


def build_child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return the exact environment passed to Kimi; unrelated secrets stay out."""

    parent = os.environ if source is None else source
    child = {name: value for name, value in parent.items() if name in _INHERITED_ENV}
    home = str(parent.get("HOME") or Path.home())
    child["HOME"] = home
    return child


def command_is_available() -> bool:
    try:
        load_plugin_config()
    except KimiACPError:
        return False
    return True
