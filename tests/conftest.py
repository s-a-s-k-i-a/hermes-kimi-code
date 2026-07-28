from __future__ import annotations

import json
import stat
import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def fake_kimi_factory(tmp_path):
    def make(mode: str = "success") -> Path:
        script = tmp_path / f"fake-kimi-{mode}"
        source = textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            import time

            MODE = {mode!r}

            def send(payload):
                sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\\n")
                sys.stdout.flush()

            def receive():
                line = sys.stdin.readline()
                if not line:
                    raise SystemExit(2)
                return json.loads(line)

            for line in sys.stdin:
                request = json.loads(line)
                if "id" not in request:
                    continue
                request_id = request["id"]
                method = request["method"]
                if method == "initialize":
                    if MODE == "malformed-json":
                        sys.stdout.write("not-json\\n")
                        sys.stdout.flush()
                        continue
                    if MODE == "oversized-line":
                        sys.stdout.write("x" * 1_048_577 + "\\n")
                        sys.stdout.flush()
                        continue
                    if MODE == "wrong-jsonrpc":
                        send({{"jsonrpc": "1.0", "id": request_id, "result": {{}}}})
                        continue
                    if MODE == "invalid-response-shape":
                        send({{
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {{}},
                            "error": {{"code": -32000, "message": "invalid"}},
                        }})
                        continue
                    if MODE == "early-exit":
                        sys.stderr.write("login required; bearer secret-value\\n")
                        sys.stderr.flush()
                        raise SystemExit(3)
                    if MODE == "wrong-agent":
                        name = "Other Agent"
                    else:
                        name = "Kimi Code CLI"
                    result = {{
                        "protocolVersion": 1,
                        "agentInfo": {{"name": name, "version": "test"}},
                        "agentCapabilities": {{"promptCapabilities": {{"image": True}}}},
                        "authMethods": (
                            []
                            if MODE == "no-login"
                            else [{{"id": "login", "name": "Log in"}}]
                        ),
                    }}
                    send({{"jsonrpc": "2.0", "id": request_id, "result": result}})
                elif method == "authenticate":
                    if MODE == "auth-error":
                        send({{
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {{"code": -32000, "message": "OAuth login expired"}},
                        }})
                    else:
                        send({{"jsonrpc": "2.0", "id": request_id, "result": {{}}}})
                elif method == "session/new":
                    result = {{
                        "sessionId": f"session-{{os.getpid()}}",
                        "configOptions": [
                            {{
                                "id": "model",
                                "currentValue": "kimi-code/k3",
                                "options": [
                                    {{"value": "kimi-code/k3"}},
                                    {{"value": "kimi-code/k3-256k"}},
                                ],
                            }},
                            {{
                                "id": "thinking",
                                **(
                                    {{}}
                                    if MODE == "thinking-no-current"
                                    else {{
                                        "currentValue": (
                                            "low" if MODE == "thinking-low-only" else "high"
                                        )
                                    }}
                                ),
                                "options": [
                                    {{"value": value}}
                                    for value in (
                                        ("low",)
                                        if MODE == "thinking-low-only"
                                        else ("low", "high", "max")
                                    )
                                ],
                            }},
                        ],
                    }}
                    send({{"jsonrpc": "2.0", "id": request_id, "result": result}})
                elif method == "session/set_config_option":
                    send({{"jsonrpc": "2.0", "id": request_id, "result": {{}}}})
                elif method == "session/prompt":
                    if MODE == "timeout":
                        time.sleep(30)
                        continue
                    if MODE == "wrong-id":
                        send({{"jsonrpc": "2.0", "id": 9999, "result": {{}}}})
                        continue
                    session_id = request["params"]["sessionId"]
                    if MODE == "invalid-session-update":
                        send({{
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": [],
                        }})
                        continue
                    send({{
                        "jsonrpc": "2.0",
                        "id": "permission-1",
                        "method": "session/request_permission",
                        "params": {{
                            "sessionId": session_id,
                            "options": (
                                [{{
                                    "optionId": "allow",
                                    "kind": "allow_once",
                                    "name": "Allow",
                                }}]
                                if MODE == "permission-no-reject"
                                else [{{
                                    "optionId": "reject",
                                    "kind": "reject_once",
                                    "name": "Reject",
                                }}]
                            ),
                        }},
                    }})
                    permission = receive()
                    outcome = permission.get("result", {{}}).get("outcome", {{}})
                    expected_outcome = (
                        {{"outcome": "cancelled"}}
                        if MODE == "permission-no-reject"
                        else {{"outcome": "selected", "optionId": "reject"}}
                    )
                    if outcome != expected_outcome:
                        raise SystemExit(8)
                    send({{
                        "jsonrpc": "2.0",
                        "id": "fs-1",
                        "method": "fs/write_text_file",
                        "params": {{"path": "/tmp/forbidden", "content": "no"}},
                    }})
                    fs_result = receive()
                    if "error" not in fs_result:
                        raise SystemExit(9)
                    send({{
                        "jsonrpc": "2.0",
                        "id": "terminal-1",
                        "method": "terminal/create",
                        "params": {{"command": "touch /tmp/forbidden"}},
                    }})
                    terminal_result = receive()
                    if "error" not in terminal_result:
                        raise SystemExit(10)
                    if MODE == "empty":
                        send({{
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {{"stopReason": "end_turn"}},
                        }})
                        continue
                    send({{
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {{
                            "sessionId": session_id,
                            "update": {{
                                "sessionUpdate": "agent_message_chunk",
                                "content": {{
                                    "type": "text",
                                    "text": f"safe answer from {{os.getpid()}}",
                                }},
                            }},
                        }},
                    }})
                    send({{
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {{"stopReason": "end_turn"}},
                    }})
            """
        )
        script.write_text(source, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    return make


@pytest.fixture
def plugin_config_factory(tmp_path):
    from hermes_kimi_code.config import PluginConfig

    def make(command: Path, **overrides):
        values = {
            "command": str(command),
            "working_directory": tmp_path,
            "timeout_seconds": 2.0,
            "startup_timeout_seconds": 2.0,
            "model": "k3",
            "thinking": "auto",
        }
        values.update(overrides)
        return PluginConfig(**values)

    return make


def parse_json(value: str) -> dict:
    parsed = json.loads(value)
    assert isinstance(parsed, dict)
    return parsed
