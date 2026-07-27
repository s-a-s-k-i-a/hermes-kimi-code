#!/usr/bin/env python3
"""Deterministic fake Kimi ACP executable used by packaged-plugin smoke tests."""

from __future__ import annotations

import json
import sys


def send(payload: dict) -> None:
    print(json.dumps(payload, separators=(",", ":")), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    request_id = request["id"]
    method = request["method"]
    if method == "initialize":
        result = {
            "protocolVersion": 1,
            "agentInfo": {"name": "Kimi Code CLI", "version": "fake-smoke"},
            "agentCapabilities": {"promptCapabilities": {"image": True}},
            "authMethods": [{"id": "login", "name": "Log in"}],
        }
    elif method == "authenticate":
        result = {}
    elif method == "session/new":
        result = {
            "sessionId": "fake-smoke-session",
            "configOptions": [
                {
                    "id": "model",
                    "currentValue": "kimi-code/k3",
                    "options": [
                        {"value": "kimi-code/k3"},
                        {"value": "kimi-code/k3-256k"},
                    ],
                },
                {
                    "id": "thinking",
                    "currentValue": "high",
                    "options": [{"value": value} for value in ("low", "high", "max")],
                },
            ],
        }
    elif method == "session/prompt":
        send(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "packaged smoke ok"},
                    }
                },
            }
        )
        result = {"stopReason": "end_turn"}
    else:
        result = {}
    send({"jsonrpc": "2.0", "id": request_id, "result": result})
