# Hermes Kimi Code installed

1. Authenticate directly in an interactive terminal with `kimi login`.
2. Enable the plugin with `hermes plugins enable kimi-code-delegate` if the installer did not.
3. Verify the non-inference handshake with `hermes kimi-code doctor`.
4. Restart a running gateway so it discovers the plugin.

The plugin is delegate-only and denies Kimi filesystem, terminal, permission, and MCP access.
To roll back, run `hermes plugins disable kimi-code-delegate` followed by
`hermes plugins remove kimi-code-delegate`.
