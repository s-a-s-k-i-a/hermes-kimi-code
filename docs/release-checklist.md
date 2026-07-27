# Release checklist

- [ ] All CI jobs are green on Python 3.11 through 3.14.
- [ ] `uv build` and `twine check dist/*` pass from a clean checkout.
- [ ] Built-wheel install, enable, Doctor, tool dispatch, disable, and removal smoke are green
      in a temporary `HERMES_HOME`.
- [ ] Real Kimi Code text delegation succeeds after an interactive `kimi login`.
- [ ] Real smoke logs contain no OAuth data, tokens, or raw environment dumps.
- [ ] `CHANGELOG.md`, package version, `plugin.yaml`, and Git tag agree.
- [ ] Repository visibility and release notes are explicitly approved before publication.
- [ ] Upstream communication links existing ACP work and does not propose a competing Core PR.
- [ ] Rollback is documented: disable `kimi-code-delegate`, uninstall the package, and remove
      only its optional `plugins.entries.kimi-code-delegate` config block.

## Upstream handoff draft

> We extracted the Kimi Code experiment into a standalone Hermes plugin, following the
> third-party integration policy discussed on #5257. The plugin registers one explicit,
> read-only `kimi_code_delegate` tool and does not register Kimi as a primary/fallback/auxiliary
> model because Kimi Code 0.29.2 does not expose a verified privileged system/developer channel
> over ACP. It owns subprocess/ACP lifecycle outside Core, leaves OAuth with the Kimi CLI, denies
> ACP permissions/filesystem/terminal requests, and has isolated Fake-ACP plus built-wheel Hermes
> smokes. It intentionally does not duplicate generic ACP PR #68222. Repository and redacted live
> evidence: <public URL after release gate>.
