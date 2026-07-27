# Security policy

Please report vulnerabilities privately to the repository owner before opening a public issue.
Do not include Kimi credentials, OAuth artifacts, raw child-process environment dumps, or
unredacted logs in a report.

The plugin never reads or copies Kimi OAuth token contents. Kimi Code remains the credential
owner and is launched with a deliberately small environment. ACP permission, filesystem, and
terminal requests are denied by the client. These controls are enforced in code; the advisory
prompt is not treated as a security boundary.
