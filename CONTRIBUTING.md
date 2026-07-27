# Contributing

Please open or link a focused issue before changing behavior. Keep Kimi-specific code in this
repository; do not require source edits in Hermes Agent Core.

## Local checks

```bash
uv sync --locked --extra test
uv run ruff check .
uv run pytest --cov=hermes_kimi_code --cov-report=term-missing
uv build
uv run twine check dist/*
```

Tests must use a temporary `HERMES_HOME` and must never read or modify a real Kimi credential
file. Live tests require explicit operator participation for `kimi login` and must not print
credentials or raw environments.

Changes that make Kimi eligible for primary, fallback, or auxiliary model routing require a
new architecture issue and proof of a native privileged instruction channel. They are not an
incremental change to the delegate-only contract.
