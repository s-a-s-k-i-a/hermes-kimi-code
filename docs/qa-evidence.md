# QA evidence

Status date: 2026-07-27

## Verified without account quota

- The isolated unit and contract suite passes on Python 3.11 and 3.13: 29 tests, 84% line
  coverage.
- Ruff reports no findings.
- Wheel and source distributions build successfully and pass `twine check`.
- The source distribution contains the plugin manifest, documentation, security policy,
  changelog, contribution guide, tests, and Fake-ACP fixture.
- Hermes Agent Core at upstream commit `551e1c6d6470a0911dabd9e0d1a756ca2f86e8b1`
  passes the relevant plugin suites through `scripts/run_tests.sh`: 124 tests passed.
- A built-wheel smoke in a temporary `HERMES_HOME` verifies entry-point discovery, enablement
  without override rights, configuration, Doctor output, registry registration, Fake-ACP tool
  dispatch, disablement, and tool removal.
- The real Kimi Code 0.29.2 ACP initialization and login handshake are accepted. Doctor still
  reports `oauth_verified: false`, because a handshake is not proof that a text prompt can be
  served.

All tests use temporary homes and redacted output. They do not read, copy, or print Kimi
credentials.

## Live account gate

The real text-prompt E2E is **not passed**. The test account currently reports that its Kimi
quota is exhausted and will reset in approximately two days. This is an external account gate,
not evidence of an OAuth or plugin defect.

After the quota reset, rerun the explicit live smoke and record only:

1. Kimi Code CLI version;
2. successful prompt completion;
3. permission-denial behavior, if the prompt requests a privileged operation;
4. plugin timeout and cleanup behavior; and
5. a redacted result with no prompt secrets, tokens, credential paths, or raw environment.

Do not publish the plugin or claim live compatibility until this gate is green.
