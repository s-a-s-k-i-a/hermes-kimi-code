# Changelog

## 0.1.0 - 2026-07-28

- Add an explicit, delegate-only `kimi_code_delegate` Hermes tool.
- Add a fail-closed ACP client with isolated subprocesses and bounded diagnostics.
- Add `hermes kimi-code doctor` for non-inference capability and login checks.
- Document why Kimi Code 0.29.2 is not eligible for primary, fallback, or auxiliary routing.
- Negotiate the ACP session's current thinking value by default and reject unsupported explicit
  values without substitution.
- Return routing and approval invariants with actionable, cause-honest textless-turn errors.
- Support both Hermes' native Git plugin installer and pip entry-point discovery.
- Fail closed on malformed Hermes configuration, tool arguments, JSON-RPC response shapes,
  and ACP session updates.
- Add real positive E2E evidence for both `k3` and `k3-256k` against current Hermes upstream.
