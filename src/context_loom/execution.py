from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fingerprints import sha256_text
from .io import read_json, write_json_atomic, write_text_atomic
from .config import resolve_root
from .fingerprints import sha256_file
from .state import load_or_create, save
from .validation import validate_worker_result


def prepare_next(workflow_dir: Path, config: dict[str, Any], baseline: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any] | None:
    state = load_or_create(workflow_dir, str(config["workflow_id"]))
    batch = next((item for item in state["batches"] if item["status"] == "pending"), None)
    if batch is None:
        return None
    tasks = {task["task_id"]: task for task in plan["tasks"]}
    selected = [tasks[task_id] for task_id in batch["task_ids"]]
    context_sources = {item["context_id"]: item for item in config.get("contexts", [])}
    root = resolve_root(workflow_dir, config)
    dynamic_context: list[dict[str, str]] = []
    for context_id in dict.fromkeys(ref for task in selected for ref in task["context_refs"]):
        if context_id not in context_sources:
            if context_id in {source["source_id"] for source in baseline["sources"]}:
                continue  # Fixed sources already belong to the baseline session.
            raise ValueError(f"unknown dynamic context reference: {context_id}")
        relative = context_sources[context_id]["path"]
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"dynamic context missing or outside root: {relative}")
        dynamic_context.append({"context_id": context_id, "path": relative,
                                "sha256": sha256_file(path), "content": path.read_text(encoding="utf-8")})
    packet = {
        "schema_version": "context-loom/packet-v1",
        "workflow_id": config["workflow_id"],
        "batch_id": batch["batch_id"],
        "mode": batch["mode"],
        "baseline_id": baseline["baseline_id"],
        "baseline_sha256": baseline["source_fingerprint"],
        "tasks": selected,
        "dynamic_context": dynamic_context,
        "instructions": "Return one Worker Result per task_id. Do not modify sibling tasks.",
    }
    packet_text = "# Worker Packet\n\n```json\n" + json.dumps(
        packet, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n```\n"
    packet_sha = sha256_text(packet_text)
    if batch.get("packet_sha256") and batch["packet_sha256"] != packet_sha:
        raise ValueError(f"packet inputs changed during recovery: {batch['batch_id']}")
    packet["packet_sha256"] = packet_sha
    out = workflow_dir / ".context-loom" / "packets"
    write_json_atomic(out / f"{batch['batch_id']}.json", packet)
    write_text_atomic(out / f"{batch['batch_id']}.md", packet_text + f"\n\nPacket SHA-256: `{packet_sha}`\n")
    batch["status"] = "running"
    batch["packet_sha256"] = packet_sha
    for task_id in batch["task_ids"]:
        if state["tasks"][task_id]["status"] == "pending":
            state["tasks"][task_id]["status"] = "running"
    save(workflow_dir, state)
    return packet


def submit_result(workflow_dir: Path, config: dict[str, Any], result: dict[str, Any]) -> list[str]:
    state = load_or_create(workflow_dir, str(config["workflow_id"]))
    packet_sha = str(result.get("packet_sha256", ""))
    task_id = str(result.get("task_id", ""))
    if not task_id or task_id not in state["tasks"]:
        raise ValueError(f"unknown task_id: {task_id}")
    task_state = state["tasks"][task_id]
    if task_state["status"] != "running":
        raise ValueError(f"task is not running: {task_id}")
    batch = next(item for item in state["batches"] if item["batch_id"] == task_state["batch_id"])
    validate_worker_result(
        result,
        task_id=task_id,
        baseline_sha256=str(state["baseline"].get("sha256")),
        packet_sha256=str(batch.get("packet_sha256")),
    )
    result_dir = workflow_dir / ".context-loom" / "results"
    write_json_atomic(result_dir / f"{task_id}.json", result)
    task_state["status"] = "validated" if result["status"] == "completed" else "failed"
    task_state["result_file"] = f"results/{task_id}.json"
    members = [state["tasks"][member] for member in batch["task_ids"]]
    if all(member["status"] in {"validated", "failed"} for member in members):
        batch["status"] = "validated" if all(member["status"] == "validated" for member in members) else "failed"
    save(workflow_dir, state)
    return [member_id for member_id in batch["task_ids"] if state["tasks"][member_id]["status"] == "validated"]


def retry_failed(workflow_dir: Path, config: dict[str, Any], task_id: str) -> None:
    """Explicitly requeue a failed task; keep an immutable copy of its failed attempt."""
    state = load_or_create(workflow_dir, str(config["workflow_id"]))
    if task_id not in state["tasks"] or state["tasks"][task_id]["status"] != "failed":
        raise ValueError(f"task is not failed: {task_id}")
    batch = next(b for b in state["batches"] if b["batch_id"] == state["tasks"][task_id]["batch_id"])
    file = workflow_dir / ".context-loom" / "results" / f"{task_id}.json"
    old = read_json(file)
    archive = workflow_dir / ".context-loom" / "attempts" / task_id
    ordinal = 1
    while (archive / f"attempt-{ordinal:03d}.json").exists():
        ordinal += 1
    write_json_atomic(archive / f"attempt-{ordinal:03d}.json", old)
    state["tasks"][task_id]["status"] = "pending"
    batch["status"] = "pending"
    save(workflow_dir, state)
