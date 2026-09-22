from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    path: str
    role: str = "source"
    sha256: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "path": self.path, "role": self.role, "sha256": self.sha256}


@dataclass(frozen=True)
class Baseline:
    schema_version: str
    workflow_id: str
    baseline_id: str
    created_at: str
    sources: tuple[SourceRef, ...]
    source_fingerprint: str
    context: str
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "baseline_id": self.baseline_id,
            "created_at": self.created_at,
            "sources": [source.to_dict() for source in self.sources],
            "source_fingerprint": self.source_fingerprint,
            "context": self.context,
            "policy": self.policy,
        }


@dataclass(frozen=True)
class TaskUnit:
    task_id: str
    title: str
    complexity: str
    source_refs: tuple[str, ...] = ()
    context_refs: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "complexity": self.complexity,
            "source_refs": list(self.source_refs),
            "context_refs": list(self.context_refs),
            "payload": self.payload,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    schema_version: str
    workflow_id: str
    baseline_id: str
    batches: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "baseline_id": self.baseline_id,
            "batches": list(self.batches),
        }


@dataclass(frozen=True)
class WorkerResult:
    schema_version: str
    task_id: str
    status: str
    baseline_sha256: str
    packet_sha256: str
    content: str
    trace: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkerResult":
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            task_id=str(raw.get("task_id", "")),
            status=str(raw.get("status", "")),
            baseline_sha256=str(raw.get("baseline_sha256", "")),
            packet_sha256=str(raw.get("packet_sha256", "")),
            content=str(raw.get("content", "")),
            trace=raw.get("trace") if isinstance(raw.get("trace"), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "status": self.status,
            "baseline_sha256": self.baseline_sha256,
            "packet_sha256": self.packet_sha256,
            "content": self.content,
            "trace": self.trace,
        }

