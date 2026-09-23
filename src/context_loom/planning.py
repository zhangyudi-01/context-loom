from __future__ import annotations

from pathlib import Path
from typing import Any

from .fingerprints import sha256_json
from .io import write_json_atomic
from .state import load_or_create, save


def _string_refs(raw: Any, field_name: str, task_id: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or any(not isinstance(value, str) or not value.strip() for value in raw):
        raise ValueError(f"{field_name} for {task_id} must be a list of non-empty strings")
    return [value.strip() for value in raw]


def build_plan(workflow_dir: Path, config: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    tasks = config.get("tasks") or []
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("at least one task is required")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    simple_buffer: list[dict[str, Any]] = []
    simple_signature: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    batches: list[dict[str, Any]] = []
    batch_size = config.get("policy", {}).get("max_simple_batch_size", 5)
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 20:
        raise ValueError("max_simple_batch_size must be an integer from 1 to 20")
    valid_sources = {source["source_id"] for source in baseline["sources"]}
    valid_contexts = {item["context_id"] for item in config.get("contexts", [])}
    if len(valid_contexts) != len(config.get("contexts", [])):
        raise ValueError("duplicate dynamic context ID")

    def flush_simple() -> None:
        nonlocal simple_buffer, simple_signature
        if not simple_buffer:
            return
        for start in range(0, len(simple_buffer), batch_size):
            members = simple_buffer[start:start + batch_size]
            batches.append({
                "batch_id": f"BATCH-{len(batches) + 1:03d}",
                "mode": "simple",
                "task_ids": [item["task_id"] for item in members],
                "rationale": "Compatible simple tasks share the baseline and packet format.",
            })
        simple_buffer = []
        simple_signature = None

    for raw in tasks:
        if not isinstance(raw, dict):
            raise ValueError("each task must be an object")
        task_id = str(raw.get("task_id", "")).strip()
        title = str(raw.get("title", "")).strip()
        complexity = str(raw.get("complexity", "simple")).strip().lower()
        if not task_id or not title or task_id in seen:
            raise ValueError(f"invalid or duplicate task: {task_id!r}")
        if complexity not in {"simple", "complex"}:
            raise ValueError(f"unsupported complexity for {task_id}: {complexity}")
        source_refs = _string_refs(raw.get("source_refs"), "source_refs", task_id)
        context_refs = _string_refs(raw.get("context_refs"), "context_refs", task_id)
        if set(source_refs) - valid_sources:
            raise ValueError(f"{task_id} references an unknown source")
        if set(context_refs) - valid_contexts - valid_sources:
            raise ValueError(f"{task_id} references an unknown context")
        payload = raw.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError(f"payload for {task_id} must be an object")
        seen.add(task_id)
        item = {
            "task_id": task_id,
            "title": title,
            "complexity": complexity,
            "source_refs": source_refs,
            "context_refs": context_refs,
            "payload": payload,
            "rationale": str(raw.get("rationale", "manual classification")),
        }
        normalized.append(item)
        if complexity == "complex":
            flush_simple()
            batches.append({
                "batch_id": f"BATCH-{len(batches) + 1:03d}",
                "mode": "dedicated-fork",
                "task_ids": [task_id],
                "rationale": "Complex tasks receive an isolated fork and focused packet.",
            })
        else:
            signature = (tuple(item["source_refs"]), tuple(item["context_refs"]))
            if simple_signature is not None and signature != simple_signature:
                flush_simple()
            simple_signature = signature
            simple_buffer.append(item)
    flush_simple()
    plan = {
        "schema_version": "context-loom/plan-v1",
        "workflow_id": config["workflow_id"],
        "baseline_id": baseline["baseline_id"],
        "baseline_sha256": baseline["source_fingerprint"],
        "tasks": normalized,
        "batches": batches,
    }
    plan["plan_sha256"] = sha256_json(plan)
    out = workflow_dir / ".context-loom"
    write_json_atomic(out / "plan.json", plan)
    state = load_or_create(workflow_dir, str(config["workflow_id"]))
    state["planning"] = {"status": "validated", "sha256": plan["plan_sha256"], "file": "plan.json"}
    state["batches"] = [dict(batch, status="pending", packet_sha256=None) for batch in batches]
    state["tasks"] = {
        task["task_id"]: {"status": "pending", "batch_id": next(b["batch_id"] for b in batches if task["task_id"] in b["task_ids"])}
        for task in normalized
    }
    save(workflow_dir, state)
    return plan
