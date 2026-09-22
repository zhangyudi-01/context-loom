from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json


CONFIG_NAME = "context-loom.json"


def load_config(workflow_dir: Path) -> dict[str, Any]:
    config = read_json(workflow_dir / CONFIG_NAME)
    if config.get("schema_version") != "context-loom/workflow-v1":
        raise ValueError(f"unsupported workflow schema in {workflow_dir / CONFIG_NAME}")
    if not str(config.get("workflow_id", "")).strip():
        raise ValueError("workflow_id is required")
    return config


def resolve_root(workflow_dir: Path, config: dict[str, Any]) -> Path:
    raw = str(config.get("root", "."))
    root = Path(raw)
    return (workflow_dir / root if not root.is_absolute() else root).resolve()

