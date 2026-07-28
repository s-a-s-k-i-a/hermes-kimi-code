"""Hermes Git-plugin loader; the canonical implementation remains under ``src``."""

if __package__:
    from .src.hermes_kimi_code import (
        KIMI_CODE_DELEGATE_SCHEMA,
        handle_kimi_code_delegate,
        register,
    )
else:  # Pytest imports a repository-root __init__.py as a top-level module.
    from src.hermes_kimi_code import (
        KIMI_CODE_DELEGATE_SCHEMA,
        handle_kimi_code_delegate,
        register,
    )

__all__ = [
    "KIMI_CODE_DELEGATE_SCHEMA",
    "handle_kimi_code_delegate",
    "register",
]
