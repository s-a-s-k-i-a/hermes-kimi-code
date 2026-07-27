# Architecture and capability contract

## Decision

Kimi Code is exposed only as an explicit Hermes tool. It is not eligible for Hermes model
routing until the ACP server provides a verified privileged instruction channel and a separate
design review enables that route.

| Capability | 0.1 contract |
| --- | --- |
| Explicit delegation | Allowed |
| Primary model | Denied |
| Fallback model | Denied |
| Auxiliary model | Denied |
| Direct file reads | Denied |
| Direct file writes | Denied |
| Terminal/process tools | Denied |
| ACP permission approval | Denied |
| MCP forwarding | Disabled |
| OAuth token access by plugin | Denied |

## Narrow waist

Hermes knows only a normal plugin tool. The standalone package owns Kimi discovery,
configuration, subprocess startup, ACP JSON-RPC, Kimi model/thinking negotiation, diagnostics,
and shutdown. There are no Kimi branches in Hermes Core.

Each invocation creates an isolated process and session. This costs startup latency but avoids
cross-conversation state bleed, shared cancellation races, and global lifecycle state in the
first releasable version.

## Authentication

The child Kimi process invokes ACP's advertised `login` method using the CLI's existing local
state. The plugin does not inspect the credential file. Kimi Code 0.29.2 can accept this ACP
handshake even when a subsequent prompt still needs an interactive login, so Doctor never calls
the handshake proof of valid OAuth. Missing, expired, or rejected authentication reported by a
real prompt is returned as `authentication_required` with the recovery instruction to run
`kimi login` interactively.

HTTP 403 is intentionally not mapped to `quota_exhausted` without provider-specific evidence.

## Failure contract

The tool returns JSON with either `ok: true` and a textual response, or `ok: false` with:

- `input`
- `configuration`
- `cli_not_found` / `cli_start`
- `authentication_required`
- `capability`
- `protocol` / `acp_request`
- `timeout` / `process_exit`
- `empty_response`

Diagnostics are bounded and redacted. Unknown server requests receive JSON-RPC method errors;
notifications are ignored without illegal responses.

## Future gate

Moving Kimi into primary/fallback/auxiliary routing requires all of the following:

1. A Kimi ACP capability that preserves system/developer priority natively.
2. Adversarial E2E proof that user content cannot demote those instructions.
3. A provider-neutral Hermes runtime extension accepted upstream.
4. A separate issue and review; this plugin must not silently expand its route eligibility.
