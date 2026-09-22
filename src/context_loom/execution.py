from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fingerprints import sha256_text
from .io import read_json, write_json_atomic, write_text_atomic
from .state import load_or_create, save
from .validation import validate_worker_result


def prepare_next(workflow_dir: Path, config: dict[str, Any], baseline: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any] | None:
    state = load_or_create(workflow_dir, str(config["workflow_id"]))
    batch = next((item for item in state["batches"] if item["status"] == "pending"), None)
    if batch is None:
        return None
    tasks = {task["task_id"]: task for task in plan["tasks"]}
    selected = [tasks[task_id] for task_id in batch["task_ids"]]
    packet = {
        "schema_version": "context-loom/packet-v1",
        "workflow_id": config["workflow_id"],
        "batch_id": batch["batch_id"],
        "mode": batch["mode"],
        "baseline_id": baseline["baseline_id"],
        "baseline_sha256": baseline["source_fingerprint"],
        "tasks": selected,
        "instructions": "Return one Worker Result per task_id. Do not modify sibling tasks.",
    }
    packet_text = "# Worker Packet\n\n```json\n" + json.dumps(
        packet, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n```\n"
    packet_sha = sha256_text(packet_text)
    packet["packet_sha256"] = packet_sha
    out = workflow_dir / ".context-loom" / "packets"
    write_json_atomic(out / f"{batch['batch_id']}.json", packet)
    write_text_atomic(out / f"{batch['batch_id']}.md", packet_text + f"\n\nPacket SHA-256: `{packet_sha}`\n")
    batch["status"] = "running"
    batch["packet_sha256"] = packet_sha
    for task_id in batch["task_ids"]:
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
