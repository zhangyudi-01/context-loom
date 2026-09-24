"""Replaceable agent host. The core never depends on a particular model vendor."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AgentTurn:
    thread_id: str
    text: str
    tool_calls: int = 0
    usage: dict[str, int] | None = None


class AgentHost(Protocol):
    def start(self, prompt: str) -> AgentTurn: ...

    def fork(self, parent_thread_id: str, prompt: str) -> AgentTurn: ...

    def resume(self, thread_id: str, prompt: str) -> AgentTurn: ...


class CodexHost:
    """Read-only, non-interactive Codex adapter; callers own state and output files."""

    def __init__(self, directory: Path, binary: str = "codex", timeout: int = 1800) -> None:
        found = shutil.which(binary) if not Path(binary).is_file() else binary
        if not found:
            raise ValueError(f"Codex CLI not found: {binary}")
        self.binary = found
        self.directory = directory.resolve()
        self.timeout = timeout
        capability = subprocess.run(
            [self.binary, "exec", "fork", "--help"], capture_output=True, text=True, timeout=15
        )
        if capability.returncode or "exec fork" not in capability.stdout:
            raise ValueError("agent host requires a CLI supporting `codex exec fork`")

    def start(self, prompt: str) -> AgentTurn:
        return self._turn(prompt, None)

    def fork(self, parent_thread_id: str, prompt: str) -> AgentTurn:
        if not parent_thread_id:
            raise ValueError("a validated baseline session is required before forking")
        return self._turn(prompt, parent_thread_id)

    def resume(self, thread_id: str, prompt: str) -> AgentTurn:
        if not thread_id:
            raise ValueError("resume requires a session id")
        return self._turn(prompt, None, thread_id)

    def _turn(self, prompt: str, parent: str | None, resume: str | None = None) -> AgentTurn:
        # A temporary final message is diagnostic evidence, never the progress ledger.
        with tempfile.TemporaryDirectory(prefix="context-loom-agent-") as temporary:
            last_message = Path(temporary) / "last-message.txt"
            command = [
                self.binary, "exec", "--json", "--color", "never", "--skip-git-repo-check",
                "--cd", str(self.directory), "--sandbox", "read-only", "--output-last-message",
                str(last_message),
            ]
            command += ["fork", parent, "-"] if parent else (["resume", resume, "-"] if resume else ["-"])
            try:
                completed = subprocess.run(
                    command, input=prompt, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=self.timeout, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError(f"agent turn exceeded {self.timeout} seconds") from exc
            if completed.returncode:
                raise ValueError(f"agent failed ({completed.returncode}): {completed.stderr[-1200:]}")
            thread_id = ""
            tool_calls = 0
            usage: dict[str, int] | None = None
            for line in completed.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    observed = event.get("thread_id", "")
                    if thread_id and thread_id != observed:
                        raise ValueError("agent reported conflicting session identities")
                    thread_id = observed
                if event.get("type") == "item.completed" and isinstance(event.get("item"), dict):
                    tool_calls += int(event["item"].get("type") in {
                        "command_execution", "mcp_tool_call", "web_search", "file_change", "computer_action"
                    })
                if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                    usage = {key: value for key, value in event["usage"].items()
                             if key in {"input_tokens", "cached_input_tokens", "output_tokens"}
                             and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
            if not thread_id or (parent and thread_id == parent) or (resume and thread_id != resume):
                raise ValueError("agent returned an invalid session identity")
            if not last_message.is_file():
                raise ValueError("agent did not produce a final response")
            return AgentTurn(thread_id, last_message.read_text(encoding="utf-8"), tool_calls, usage)
