# Hermes Kimi Code

Standalone Hermes Agent plugin for **explicit, read-only delegation** to a locally
authenticated Kimi Code CLI over ACP.

The plugin deliberately does **not** register Kimi as a Hermes model provider. Kimi Code
0.29.2 does not expose a verified privileged system/developer instruction channel over ACP,
so using it for Hermes primary, fallback, or auxiliary model turns would weaken instruction
priority. Hermes remains the orchestrator and calls `kimi_code_delegate` only when delegation
is useful.

## Status

This is an unreleased alpha. Automated protocol and installation tests are required before
the first release. The negative live smoke confirms that an exhausted account returns a precise
HTTP 403 in the direct Kimi CLI but only a textless `end_turn` over ACP. The plugin therefore
reports an unknown provider status and never infers quota from ACP alone. A successful live
answer remains gated on refreshed quota.

## Security boundary

- One fresh `kimi acp` process and ACP session is created per tool call.
- The plugin never reads, copies, refreshes, or prints OAuth token contents.
- Kimi receives a small allowlisted environment and uses its own CLI-owned login under `HOME`
  or `KIMI_CODE_HOME`.
- ACP permission requests are rejected. Filesystem and terminal requests receive errors.
- No MCP servers are forwarded.
- Command and working directory are operator-owned `config.yaml` settings, never model input.
- Timeouts, wire-line limits, prompt limits, bounded stderr, and redaction are enforced.
- Empty responses are errors rather than successful turns.

The read-only instruction included in the delegated prompt is guidance, not a security
control. The ACP client-side denials are the security control.

## Prerequisites

- Hermes Agent with pip plugin entry-point support
- Python 3.11 or newer
- Kimi Code CLI 0.29.2 or a compatible newer release
- An interactive Kimi CLI login completed directly with:

```bash
kimi login
```

## Installation

Until a release exists, install from a trusted local checkout:

```bash
python -m pip install /path/to/hermes-kimi-code
hermes plugins enable kimi-code-delegate
hermes kimi-code doctor
```

Pip entry-point discovery uses the plugin id `kimi-code-delegate`. No Hermes Core files are
patched.

## Configuration

All behavioral settings live in `config.yaml`, following Hermes policy for non-secret
configuration:

```yaml
plugins:
  enabled:
    - kimi-code-delegate
  entries:
    kimi-code-delegate:
      # Optional. Defaults to ~/.kimi-code/bin/kimi, then PATH.
      command: /absolute/path/to/kimi
      # Optional. Defaults to the Hermes process working directory.
      working_directory: /absolute/read-only-context/root
      timeout_seconds: 300
      startup_timeout_seconds: 10
      model: k3
      # Optional. Auto negotiates Kimi ACP's current session value.
      thinking: auto
```

The command is executed directly as `[command, "acp"]`; no shell and no configurable argument
string are involved. Supported models are `k3` and `k3-256k`. Thinking defaults to `auto`, which
uses the current value advertised by the ACP session. Explicit values are `low`, `high`, and
`max` in Kimi Code 0.29.2. Future option ids are accepted by configuration but applied only when
the installed ACP session advertises that exact value; unsupported values fail closed.

## Use

Hermes sees one tool:

```text
kimi_code_delegate(prompt, model?, thinking?)
```

The prompt must be self-contained. Kimi cannot read local files, execute commands, call MCP
servers, or make changes through this plugin. If context is needed, Hermes must include the
relevant non-secret text in the delegated prompt.

Run a no-inference preflight at any time:

```bash
hermes kimi-code doctor
hermes kimi-code doctor --json
```

The doctor checks executable startup, ACP identity/capabilities, and whether Kimi accepts the
ACP `login` handshake. Kimi Code 0.29.2 may accept that handshake before a real prompt even
when the interactive CLI later requires `kimi login`, so Doctor reports OAuth as **unverified**.
Only a successful delegated prompt proves the live login. Doctor itself performs no inference.

When Kimi returns no text and no ACP error detail, the tool reports `empty_response`, states that
the provider status is unknown, and asks the user to check interactive login and account quota.
The structured result also confirms that Hermes model routing was not changed and no ACP
approval request was forwarded to the user.

## Uninstall

```bash
hermes plugins disable kimi-code-delegate
python -m pip uninstall hermes-kimi-code
```

Removing the package removes the tool. Hermes Core remains untouched. You may separately
remove the corresponding `plugins.entries.kimi-code-delegate` configuration block.

## Project tracking and upstream relationship

- Tracking umbrella: [s-a-s-k-i-a/hermes-agent#47](https://github.com/s-a-s-k-i-a/hermes-agent/issues/47)
- Implementation: [#44](https://github.com/s-a-s-k-i-a/hermes-agent/issues/44)
- Verification: [#45](https://github.com/s-a-s-k-i-a/hermes-agent/issues/45)
- Release: [#46](https://github.com/s-a-s-k-i-a/hermes-agent/issues/46)
- Thinking negotiation: [#48](https://github.com/s-a-s-k-i-a/hermes-agent/issues/48)
- Quota-state UX: [#49](https://github.com/s-a-s-k-i-a/hermes-agent/issues/49)

Generic ACP Core work already exists upstream in
[NousResearch/hermes-agent#68222](https://github.com/NousResearch/hermes-agent/pull/68222).
This plugin does not duplicate that PR and does not add a named Kimi integration to Core.

## Author

Saskia Teichmann ([@s-a-s-k-i-a](https://github.com/s-a-s-k-i-a)).
