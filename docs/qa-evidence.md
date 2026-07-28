# QA evidence

Status date: 2026-07-28

## Verified without account quota

- The isolated unit and contract suite passes locally: 48 tests, 84% line
  coverage.
- Ruff reports no findings.
- Wheel and source distributions build successfully and pass `twine check`.
- The source distribution contains the plugin manifest, documentation, security policy,
  changelog, contribution guide, tests, and Fake-ACP fixture.
- Hermes Agent Core at upstream commit `1dfe781edd5e96d09511cf27d800a03e63b09789`
  passes eight relevant plugin/registry suites through `scripts/run_tests.sh`: 328 tests passed.
- A built-wheel smoke in a temporary `HERMES_HOME` verifies entry-point discovery, enablement
  without override rights, configuration, Doctor output, registry registration, Fake-ACP tool
  dispatch, disablement, and tool removal.
- The real Kimi Code 0.29.2 ACP initialization and login handshake are accepted. Doctor still
  reports `oauth_verified: false`, because a handshake is not proof that a text prompt can be
  served.
- Native `hermes plugins install` covers Git clone, enable, discovery, Doctor, live dispatch,
  disable, tool removal, and uninstall in a temporary `HERMES_HOME`.
- The locked test dependency set has no known vulnerabilities according to `pip-audit`; `gitleaks`
  reports no secrets across repository history.

All tests use temporary homes and redacted output. They do not read, copy, or print Kimi
credentials.

## Exhausted-quota E2E

The exhausted account is a verified negative live case:

- Kimi Code 0.29.2 direct prompt mode reports an explicit HTTP 403 usage-limit condition.
- The same condition over ACP returns `stopReason=end_turn` with no text, stderr, or error detail.
- Both `k3` and `k3-256k` reach that ACP path through a built wheel loaded by Hermes from a
  temporary `HERMES_HOME`.
- Both return the same structured tool result: `ok: false`, `error_type: empty_response`, unknown
  provider status, and interactive login/quota recovery guidance.
- The result records `hermes_model_changed: false` and `approval_requests_forwarded: false`; a
  sentinel Hermes model/provider pair remains unchanged before and after each dispatch.
- The real quota path sends no ACP permission request. Fake-ACP coverage proves that explicit
  reject options are selected, requests without a reject option are cancelled, and filesystem
  and terminal calls receive errors without opening user approval UI.
- Plugin enablement grants no built-in tool override rights.
- No `kimi acp` subprocess remains after either live call.

ACP alone does not prove quota exhaustion because it omits the provider error. The plugin does
not launch a second inference or read private Kimi logs to guess that missing cause.

## Positive live E2E

The successful text-prompt gate is passed using Kimi Code 0.29.2, the native Git-installed
plugin, a temporary `HERMES_HOME`, and Hermes upstream commit
`1dfe781edd5e96d09511cf27d800a03e63b09789`:

- `k3` returned the exact 18-character success marker with negotiated thinking `high`.
- `k3-256k` returned the exact 16-character success marker with negotiated thinking `high`.
- Both structured results reported `delegate_only: true`, `hermes_model_changed: false`, and
  `approval_requests_forwarded: false`.
- A sentinel Hermes model/provider pair was byte-for-byte unchanged before and after each
  dispatch.
- A read-only boundary prompt returned its exact marker and emitted zero permission, terminal,
  and filesystem requests over ACP.
- No `kimi acp` process remained after completion.

The deterministic Fake-ACP suite separately forces permission requests with and without a reject
option plus filesystem and terminal calls. The client selects `reject_once`, cancels when no
reject option exists, and returns local JSON-RPC errors without opening Hermes approval UI.

Only the explicit success markers and structured invariants were retained. No OAuth data, account
identifier, full provider response, credential path, or raw environment was recorded.
