# Release checklist

- [x] All CI jobs are green on Python 3.11 through 3.14.
- [x] `uv build` and `twine check dist/*` pass from a clean checkout.
- [x] Built-wheel install, enable, Doctor, tool dispatch, disable, and removal smoke are green
      in a temporary `HERMES_HOME`.
- [x] Native Git install, enable, Doctor, dispatch, disable, and removal are green against current
      Hermes upstream.
- [x] Real Kimi Code text delegation succeeds for `k3` and `k3-256k` after interactive login.
- [x] Real smoke logs contain no OAuth data, tokens, account identifiers, or raw environment dumps.
- [x] Locked dependencies have no known vulnerabilities and repository history has no detected
      secrets.
- [x] `CHANGELOG.md`, package version, `plugin.yaml`, and the planned `v0.1.0` Git tag agree.
- [x] Repository visibility and release notes are explicitly approved before publication.
- [x] Upstream communication links existing ACP work and does not propose a competing Core PR.
- [x] Rollback is documented: disable `kimi-code-delegate`, uninstall the package, and remove
      only its optional `plugins.entries.kimi-code-delegate` config block.

## Upstream handoff draft

> We extracted the Kimi Code experiment into a standalone Hermes plugin, following the
> third-party integration policy discussed on #5257. The plugin registers one explicit,
> read-only `kimi_code_delegate` tool and does not register Kimi as a primary/fallback/auxiliary
> model because Kimi Code 0.29.2 does not expose a verified privileged system/developer channel
> over ACP. It owns subprocess/ACP lifecycle outside Core, leaves OAuth with the Kimi CLI, denies
> ACP permissions/filesystem/terminal requests, and has isolated Fake-ACP plus built-wheel Hermes
> smokes plus positive live `k3`/`k3-256k` turns against current Hermes upstream. It intentionally
> does not duplicate generic ACP PR #68222. Repository and redacted evidence:
> https://github.com/s-a-s-k-i-a/hermes-kimi-code.
