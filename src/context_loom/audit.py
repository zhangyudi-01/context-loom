"""Append-only agent invocation audit; never used to schedule or recover work."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import AgentHost, AgentTurn


AUDIT_NAME = ".context-loom/invocations.jsonl"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class InvocationAudit:
    """One run's correlation ID, persisted across append-only invocation events."""

    def __init__(self, directory: Path, workflow_id: str) -> None:
        self.path = directory / AUDIT_NAME
        self.workflow_id = workflow_id
        self.run_id = str(uuid.uuid4())

    def _append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

    def scope(self, host: AgentHost, stage: str, *, batch_id: str | None = None,
              task_id: str | None = None) -> AgentHost:
        return _ScopedHost(self, host, stage, batch_id, task_id)


class _ScopedHost:
    def __init__(self, audit: InvocationAudit, host: AgentHost, stage: str,
                 batch_id: str | None, task_id: str | None) -> None:
        self.audit, self.host, self.stage = audit, host, stage
        self.batch_id, self.task_id = batch_id, task_id

    def _invoke(self, operation: str, prompt: str, parent: str | None = None) -> AgentTurn:
        invocation_id = str(uuid.uuid4())
        event = {"schema_version": "context-loom/invocation-v1", "workflow_id": self.audit.workflow_id,
                 "run_id": self.audit.run_id, "invocation_id": invocation_id, "stage": self.stage,
                 "batch_id": self.batch_id, "task_id": self.task_id, "operation": operation,
                 "parent_thread_id": parent, "host": type(self.host).__name__}
        began = time.monotonic()
        self.audit._append(dict(event, event="started", timestamp=_timestamp()))
        try:
            turn = getattr(self.host, operation)(parent, prompt) if parent is not None else self.host.start(prompt)
        except BaseException as exc:
            self.audit._append(dict(event, event="failed", timestamp=_timestamp(),
                                    elapsed_ms=round((time.monotonic() - began) * 1000),
                                    error_type=type(exc).__name__))
            raise
        self.audit._append(dict(event, event="completed", timestamp=_timestamp(),
                                elapsed_ms=round((time.monotonic() - began) * 1000),
                                thread_id=turn.thread_id, tool_calls=turn.tool_calls,
                                usage=turn.usage))
        return turn

    def start(self, prompt: str) -> AgentTurn:
        return self._invoke("start", prompt)

    def fork(self, parent_thread_id: str, prompt: str) -> AgentTurn:
        return self._invoke("fork", prompt, parent_thread_id)

    def resume(self, thread_id: str, prompt: str) -> AgentTurn:
        return self._invoke("resume", prompt, thread_id)


def summarize(directory: Path) -> dict[str, Any]:
    """Read diagnostic evidence on demand; do not feed it to the scheduler."""
    path = directory / AUDIT_NAME
    if not path.is_file():
        return {"path": str(path), "recorded": False, "note": "Earlier invocations were not audited."}
    invocations: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid audit JSON at line {number}") from exc
            ident = event.get("invocation_id")
            if not isinstance(ident, str) or event.get("event") not in {"started", "completed", "failed"}:
                raise ValueError(f"invalid audit event at line {number}")
            record = invocations.setdefault(ident, {})
            if event["event"] in record:
                raise ValueError(f"duplicate audit event at line {number}")
            record[event["event"]] = event
    counts: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    by_stage: dict[str, Counter[str]] = {}
    incomplete: list[dict[str, Any]] = []
    for ident, record in invocations.items():
        start = record.get("started")
        if not start:
            raise ValueError(f"audit terminal event has no start: {ident}")
        if "completed" in record and "failed" in record:
            raise ValueError(f"audit invocation has multiple terminal events: {ident}")
        status = "completed" if "completed" in record else "failed" if "failed" in record else "interrupted"
        operation = start["operation"]
        counts[operation] += 1
        counts[status] += 1
        stage_counts = by_stage.setdefault(start["stage"], Counter())
        stage_counts[operation] += 1
        stage_counts[status] += 1
        if status != "completed":
            incomplete.append({"invocation_id": ident, "run_id": start["run_id"],
                               "stage": start["stage"], "operation": operation,
                               "batch_id": start.get("batch_id"), "task_id": start.get("task_id"),
                               "status": status, "error_type": record.get("failed", {}).get("error_type")})
        for key, value in (record.get("completed", {}).get("usage") or {}).items():
            usage[key] += value
    return {"path": str(path), "recorded": True, "invocations": len(invocations),
            "counts": dict(counts), "usage": dict(usage),
            "by_stage": {stage: dict(c) for stage, c in by_stage.items()},
            "incomplete": incomplete,
            "note": "Counts cover recorded attempts only, not invocations before auditing was enabled."}


def summarize_workflow(directory: Path) -> dict[str, Any]:
    """Accept a single workflow or the three-phase software-testing trial root."""
    if (directory / AUDIT_NAME).is_file() or not any(
            (directory / phase).is_dir() for phase in ("preanalysis", "test-points", "test-cases")):
        return summarize(directory)
    phases = {phase: summarize(directory / phase) for phase in ("preanalysis", "test-points", "test-cases")}
    counts: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    incomplete: list[dict[str, Any]] = []
    for phase, result in phases.items():
        counts.update(result.get("counts", {}))
        usage.update(result.get("usage", {}))
        incomplete.extend(dict(item, phase=phase) for item in result.get("incomplete", []))
    return {"path": str(directory), "recorded": any(item["recorded"] for item in phases.values()),
            "invocations": sum(item.get("invocations", 0) for item in phases.values()),
            "counts": dict(counts), "usage": dict(usage), "phases": phases, "incomplete": incomplete,
            "note": "Phases without an audit file may have older unrecorded invocations."}
