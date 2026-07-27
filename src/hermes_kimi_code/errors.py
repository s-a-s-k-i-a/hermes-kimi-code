"""Stable, non-secret error contract for the Kimi ACP boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KimiACPError(RuntimeError):
    """An actionable failure that is safe to return through a Hermes tool."""

    error_type: str
    message: str
    recovery: str = ""

    def __str__(self) -> str:
        return self.message


AUTH_RECOVERY = "Run `kimi login` in an interactive terminal, then retry."
