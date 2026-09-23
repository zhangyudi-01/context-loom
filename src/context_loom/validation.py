from __future__ import annotations

from typing import Any


def validate_worker_result(
    result: dict[str, Any],
    *,
    task_id: str,
    baseline_sha256: str,
    packet_sha256: str,
) -> None:
    required = ("schema_version", "task_id", "status", "baseline_sha256", "packet_sha256", "content")
    missing = [key for key in required if key not in result]
    if missing:
        raise ValueError(f"worker result is missing: {', '.join(missing)}")
    if result["schema_version"] != "context-loom/worker-result-v1":
        raise ValueError("unsupported worker result schema")
    if result["task_id"] != task_id:
        raise ValueError("worker result task_id does not match the active task")
    if result["baseline_sha256"] != baseline_sha256:
        raise ValueError("worker result baseline_sha256 does not match the active baseline")
    if result["packet_sha256"] != packet_sha256:
        raise ValueError("worker result packet_sha256 does not match the active packet")
    if result["status"] not in {"completed", "failed"}:
        raise ValueError("worker result status must be completed or failed")
    if not isinstance(result["content"], str):
        raise ValueError("worker result content must be a string")
    if result["status"] == "completed" and not result["content"].strip():
        raise ValueError("completed worker result must have content")
    if "trace" in result and not isinstance(result["trace"], dict):
        raise ValueError("worker trace must be an object")
