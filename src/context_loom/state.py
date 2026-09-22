from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import read_json, write_json_atomic


STATE_NAME = ".context-loom/state.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def state_path(workflow_dir: Path) -> Path:
    return workflow_dir / STATE_NAME


def new_state(workflow_id: str) -> dict[str, Any]:
    return {
        "schema_version": "context-loom/state-v1",
        "workflow_id": workflow_id,
        "created_at": now(),
        "updated_at": now(),
        "baseline": {"status": "pending", "sha256": None},
        "planning": {"status": "pending", "sha256": None},
        "assembly": {"status": "pending", "output": None},
        "batches": [],
        "tasks": {},
    }


def load_or_create(workflow_dir: Path, workflow_id: str) -> dict[str, Any]:
    path = state_path(workflow_dir)
    if not path.exists():
        state = new_state(workflow_id)
        save(workflow_dir, state)
        return state
    state = read_json(path)
    if state.get("schema_version") != "context-loom/state-v1":
        raise ValueError(f"unsupported state schema in {path}")
    if state.get("workflow_id") != workflow_id:
        raise ValueError("state workflow_id does not match context-loom.json")
    return state


def save(workflow_dir: Path, state: dict[str, Any]) -> None:
    state = deepcopy(state)
    state["updated_at"] = now()
    write_json_atomic(state_path(workflow_dir), state)

