"""Small, fail-closed ACP client dedicated to explicit Kimi delegation."""

from __future__ import annotations

import json
import os
import queue
import re
import signal
import subprocess
import threading
import time
from collections import deque
from contextlib import suppress
from typing import Any

from .config import SUPPORTED_MODELS, PluginConfig, build_child_environment
from .errors import AUTH_RECOVERY, KimiACPError

_MAX_PROMPT_CHARS = 100_000
_MAX_WIRE_LINE_CHARS = 1_048_576
_MAX_DIAGNOSTIC_CHARS = 4_096
_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+"),
    re.compile(r"(?i)((?:access|refresh|id)[_-]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|secret|password)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s/@]+(@)", re.I),
)


def sanitize_diagnostic(value: Any) -> str:
    """Bound and redact untrusted child-process output before returning it."""

    text = str(value or "").strip()
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(r"\1[REDACTED]\2", text)
        else:
            text = pattern.sub(r"\1[REDACTED]", text)
    if len(text) > _MAX_DIAGNOSTIC_CHARS:
        half = _MAX_DIAGNOSTIC_CHARS // 2
        text = f"{text[:half]}\n...[diagnostic truncated]...\n{text[-half:]}"
    return text


def _jsonrpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": code, "message": message},
    }


def _permission_denied(message_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    reject_id = next(
        (
            str(option.get("optionId") or "").strip()
            for option in params.get("options") or []
            if isinstance(option, dict)
            and str(option.get("kind") or "").strip() == "reject_once"
            and str(option.get("optionId") or "").strip()
        ),
        "",
    )
    outcome = (
        {"outcome": "selected", "optionId": reject_id} if reject_id else {"outcome": "cancelled"}
    )
    return {"jsonrpc": "2.0", "id": message_id, "result": {"outcome": outcome}}


class KimiACPClient:
    """One-process-per-call ACP client with no ambient mutable session state."""

    def __init__(self, config: PluginConfig):
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=40)
        self._next_id = 0
        self._write_lock = threading.Lock()

    def __enter__(self) -> KimiACPClient:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        try:
            process = subprocess.Popen(
                [self.config.command, "acp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(self.config.working_directory),
                env=build_child_environment(),
                **kwargs,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            raise KimiACPError(
                "cli_start",
                "Kimi Code CLI could not be started.",
                "Verify the configured command and executable permissions.",
            ) from exc
        if process.stdin is None or process.stdout is None or process.stderr is None:
            self._terminate(process)
            raise KimiACPError("protocol", "Kimi Code did not expose ACP stdio pipes.")
        self._process = process
        threading.Thread(target=self._read_stdout, args=(process,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(process,), daemon=True).start()

    def close(self) -> None:
        process, self._process = self._process, None
        self._terminate(process)

    @staticmethod
    def _terminate(process: subprocess.Popen[str] | None) -> None:
        if process is None:
            return
        try:
            if process.poll() is not None:
                process.wait(timeout=0)
                return
        except Exception:
            pass
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=2)
            return
        except Exception:
            pass
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=2)
        except Exception:
            pass

    def _read_stdout(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        while True:
            line = process.stdout.readline(_MAX_WIRE_LINE_CHARS + 1)
            if not line:
                return
            if len(line) > _MAX_WIRE_LINE_CHARS:
                self._inbox.put({"_protocol_error": "ACP response line exceeded the size limit."})
                return
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self._inbox.put({"_protocol_error": "Kimi returned malformed ACP JSON."})
                continue
            if not isinstance(payload, dict):
                self._inbox.put({"_protocol_error": "Kimi returned a non-object ACP frame."})
                continue
            self._inbox.put(payload)

    def _read_stderr(self, process: subprocess.Popen[str]) -> None:
        assert process.stderr is not None
        while True:
            line = process.stderr.readline(_MAX_DIAGNOSTIC_CHARS + 1)
            if not line:
                return
            self._stderr_tail.append(line.rstrip("\n"))

    def _write(self, payload: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise KimiACPError("protocol", "Kimi ACP connection is not available.")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > _MAX_WIRE_LINE_CHARS:
            raise KimiACPError("input", "ACP request exceeded the size limit.")
        try:
            with self._write_lock:
                process.stdin.write(encoded + "\n")
                process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise KimiACPError("process_exit", "Kimi ACP closed its input unexpectedly.") from exc

    def _handle_server_message(
        self,
        message: dict[str, Any],
        *,
        text_parts: list[str] | None,
    ) -> bool:
        method = message.get("method")
        if not isinstance(method, str):
            return False
        if method == "session/update":
            params = message.get("params") or {}
            update = params.get("update") or {}
            if not isinstance(update, dict):
                return True
            kind = str(update.get("sessionUpdate") or "")
            content = update.get("content") or {}
            text = str(content.get("text") or "") if isinstance(content, dict) else ""
            if kind == "agent_message_chunk" and text and text_parts is not None:
                text_parts.append(text)
            return True

        # JSON-RPC notifications are never answered.
        if "id" not in message:
            return True
        message_id = message.get("id")
        params = message.get("params")
        params = params if isinstance(params, dict) else {}
        if method == "session/request_permission":
            response = _permission_denied(message_id, params)
        elif method.startswith(("fs/", "terminal/")):
            response = _jsonrpc_error(
                message_id,
                -32000,
                "Direct filesystem and terminal access is disabled by the delegate-only client.",
            )
        else:
            response = _jsonrpc_error(message_id, -32601, f"Unsupported ACP method: {method}")
        self._write(response)
        return True

    def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
        text_parts: list[str] | None = None,
    ) -> Any:
        process = self._process
        if process is None:
            raise KimiACPError("protocol", "Kimi ACP process has not been started.")
        self._next_id += 1
        request_id = self._next_id
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                message = self._inbox.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if "_protocol_error" in message:
                raise KimiACPError("protocol", str(message["_protocol_error"]))
            if self._handle_server_message(message, text_parts=text_parts):
                continue
            if message.get("id") != request_id:
                raise KimiACPError(
                    "protocol", "Kimi returned a response for an unexpected request id."
                )
            if "error" in message:
                error = message.get("error")
                detail = error.get("message") if isinstance(error, dict) else error
                safe_detail = sanitize_diagnostic(detail) or "unspecified error"
                if method == "authenticate" or re.search(
                    r"login|oauth|authenticat", safe_detail, re.I
                ):
                    raise KimiACPError(
                        "authentication_required",
                        f"Kimi Code authentication failed: {safe_detail}",
                        AUTH_RECOVERY,
                    )
                raise KimiACPError("acp_request", f"Kimi ACP {method} failed: {safe_detail}")
            return message.get("result")

        stderr = sanitize_diagnostic("\n".join(self._stderr_tail))
        if process.poll() is not None:
            message = "Kimi Code ACP exited before replying."
            if stderr:
                message = f"{message} {stderr}"
            recovery = AUTH_RECOVERY if re.search(r"login|oauth|auth", stderr, re.I) else ""
            error_type = "authentication_required" if recovery else "process_exit"
            raise KimiACPError(error_type, message, recovery)
        if method == "session/prompt":
            with suppress(KimiACPError):
                self._write(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/cancel",
                        "params": {"sessionId": params.get("sessionId")},
                    }
                )
        raise KimiACPError(
            "timeout",
            f"Timed out waiting for Kimi ACP {method}.",
            "Retry once; if it persists, run `hermes kimi-code doctor`.",
        )

    @staticmethod
    def _config_option(options: list[Any], config_id: str) -> dict[str, Any] | None:
        return next(
            (
                option
                for option in options
                if isinstance(option, dict) and option.get("id") == config_id
            ),
            None,
        )

    def _initialize_and_authenticate(self) -> dict[str, Any]:
        initialize = self._request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
                "clientInfo": {
                    "name": "hermes-kimi-code",
                    "title": "Hermes Kimi Code Delegate",
                    "version": "0.1.0",
                },
            },
            timeout_seconds=self.config.startup_timeout_seconds,
        )
        if not isinstance(initialize, dict):
            raise KimiACPError("protocol", "Kimi ACP initialize returned a non-object result.")
        if initialize.get("protocolVersion") != 1:
            raise KimiACPError("capability", "Kimi ACP does not support protocol version 1.")
        agent_info = initialize.get("agentInfo")
        agent_name = str(agent_info.get("name") or "") if isinstance(agent_info, dict) else ""
        if "kimi" not in agent_name.lower():
            raise KimiACPError(
                "capability", "The ACP executable did not identify itself as Kimi Code."
            )
        auth_methods = initialize.get("authMethods") or []
        has_login = any(
            isinstance(method, dict) and str(method.get("id") or "") == "login"
            for method in auth_methods
        )
        if not has_login:
            raise KimiACPError(
                "capability",
                "Kimi ACP did not advertise its CLI-owned login method.",
                "Upgrade Kimi Code and retry.",
            )
        self._request(
            "authenticate",
            {"methodId": "login"},
            timeout_seconds=self.config.startup_timeout_seconds,
        )
        return initialize

    def probe(self) -> dict[str, Any]:
        """Validate executable, protocol identity, and existing CLI login only."""

        self.start()
        initialize = self._initialize_and_authenticate()
        agent_info = initialize.get("agentInfo") or {}
        capabilities = initialize.get("agentCapabilities") or {}
        return {
            "agent": str(agent_info.get("name") or "Kimi Code"),
            "version": str(agent_info.get("version") or "unknown"),
            "acp_login_handshake": "accepted",
            "oauth_verified": False,
            "delegate_only": True,
            "prompt_capabilities": capabilities.get("promptCapabilities") or {},
        }

    def delegate(self, prompt: str, *, model: str, thinking: str) -> dict[str, Any]:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise KimiACPError("input", "prompt must not be empty.")
        if len(prompt) > _MAX_PROMPT_CHARS:
            raise KimiACPError(
                "input", f"prompt exceeds the {_MAX_PROMPT_CHARS:,} character limit."
            )
        if model not in SUPPORTED_MODELS:
            raise KimiACPError("input", "model must be k3 or k3-256k.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", thinking):
            raise KimiACPError("input", "thinking must be auto or a valid ACP option id.")

        self.start()
        self._initialize_and_authenticate()
        session = self._request(
            "session/new",
            {"cwd": str(self.config.working_directory), "mcpServers": []},
            timeout_seconds=self.config.startup_timeout_seconds,
        )
        if not isinstance(session, dict) or not str(session.get("sessionId") or "").strip():
            raise KimiACPError("protocol", "Kimi ACP did not return a sessionId.")
        session_id = str(session["sessionId"])
        options = session.get("configOptions") or []
        model_option = self._config_option(options, "model")
        offered_models = {
            str(item.get("value") or "")
            for item in (model_option or {}).get("options") or []
            if isinstance(item, dict)
        }
        selected_model = SUPPORTED_MODELS[model]
        if selected_model not in offered_models:
            raise KimiACPError("capability", f"Kimi ACP does not offer model '{model}'.")
        self._request(
            "session/set_config_option",
            {"sessionId": session_id, "configId": "model", "value": selected_model},
            timeout_seconds=self.config.startup_timeout_seconds,
        )

        thinking_option = self._config_option(options, "thinking")
        offered_thinking = {
            str(item.get("value") or "")
            for item in (thinking_option or {}).get("options") or []
            if isinstance(item, dict)
        }
        current_thinking = str((thinking_option or {}).get("currentValue") or "").strip()
        if thinking == "auto":
            if not current_thinking or current_thinking not in offered_thinking:
                raise KimiACPError(
                    "capability",
                    "Kimi ACP did not provide a usable current thinking value.",
                )
            selected_thinking = current_thinking
        else:
            selected_thinking = thinking
        if selected_thinking not in offered_thinking:
            raise KimiACPError("capability", f"Kimi ACP does not offer thinking '{thinking}'.")
        self._request(
            "session/set_config_option",
            {"sessionId": session_id, "configId": "thinking", "value": selected_thinking},
            timeout_seconds=self.config.startup_timeout_seconds,
        )

        advisory_prompt = (
            "READ-ONLY DELEGATION BOUNDARY: Return analysis or suggested text only. "
            "Do not execute tools, terminal commands, filesystem operations, network mutations, "
            "or other side effects. The ACP client will deny such requests.\n\n"
            f"Delegated task:\n{prompt}"
        )
        text_parts: list[str] = []
        result = self._request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": advisory_prompt}],
            },
            timeout_seconds=self.config.timeout_seconds,
            text_parts=text_parts,
        )
        response = "".join(text_parts).strip()
        if not response:
            stop_reason = (
                str(result.get("stopReason") or "unknown")
                if isinstance(result, dict)
                else "unknown"
            )
            raise KimiACPError(
                "empty_response",
                f"Kimi ACP ended with '{stop_reason}' but returned no text. "
                "The provider status is unknown because ACP supplied no error detail.",
                "Check Kimi login and account quota in an interactive terminal, then retry. "
                "Hermes remains on its current model.",
            )
        return {"response": response, "model": selected_model, "thinking": selected_thinking}


def run_probe(config: PluginConfig) -> dict[str, Any]:
    with KimiACPClient(config) as client:
        return client.probe()


def run_delegation(
    config: PluginConfig,
    prompt: str,
    *,
    model: str,
    thinking: str,
) -> dict[str, Any]:
    with KimiACPClient(config) as client:
        return client.delegate(prompt, model=model, thinking=thinking)
