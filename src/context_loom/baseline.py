from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import resolve_root
from .contracts import Baseline, SourceRef
from .fingerprints import sha256_file, sha256_json
from .io import write_json_atomic, write_text_atomic
from .state import load_or_create, save


def compile_baseline(workflow_dir: Path, config: dict[str, Any]) -> Baseline:
    root = resolve_root(workflow_dir, config)
    raw_sources = config.get("sources") or config.get("baseline", {}).get("sources") or []
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("at least one source is required")
    refs: list[SourceRef] = []
    seen: set[str] = set()
    sections: list[str] = []
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise ValueError("each source must be an object")
        source_id = str(raw.get("source_id", "")).strip()
        relative = str(raw.get("path", "")).strip()
        if not source_id or not relative or source_id in seen:
            raise ValueError("each source needs source_id and path")
        seen.add(source_id)
        path = (root / relative).resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"source escapes workflow root: {relative}")
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = sha256_file(path)
        role = str(raw.get("role", "source"))
        refs.append(SourceRef(source_id, relative, role, digest))
        content = path.read_text(encoding="utf-8")
        sections.append(f"## {source_id}\n\nSource path: `{relative}`\n\n{content.rstrip()}\n")
    source_fingerprint = sha256_json([ref.to_dict() for ref in refs])
    baseline = Baseline(
        schema_version="context-loom/baseline-v1",
        workflow_id=str(config["workflow_id"]),
        baseline_id=f"BASELINE-{str(config['workflow_id']).upper()}",
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        sources=tuple(refs),
        source_fingerprint=source_fingerprint,
        context="\n\n".join(sections),
        policy=config.get("policy", {}),
    )
    out = workflow_dir / ".context-loom"
    write_json_atomic(out / "baseline.json", baseline.to_dict())
    write_text_atomic(out / "baseline.md", f"# Baseline {baseline.baseline_id}\n\n" + baseline.context + "\n")
    state = load_or_create(workflow_dir, baseline.workflow_id)
    state["baseline"] = {"status": "validated", "sha256": source_fingerprint, "file": "baseline.json"}
    save(workflow_dir, state)
    return baseline


def assert_baseline_current(workflow_dir: Path, config: dict[str, Any], baseline: dict[str, Any]) -> None:
    """Fail closed on any authoritative-source change before reusing a session or a plan."""
    root = resolve_root(workflow_dir, config)
    sources = config.get("sources") or config.get("baseline", {}).get("sources") or []
    old = baseline.get("sources", [])
    if len(old) != len(sources):
        raise ValueError("baseline source list changed; start a new workflow")
    if baseline.get("source_fingerprint") != sha256_json(old):
        raise ValueError("baseline fingerprint is invalid")
    for raw, recorded in zip(sources, old):
        relative = raw.get("path", "")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"baseline source is missing or out of bounds: {relative}")
        if (recorded["source_id"] != raw.get("source_id") or
                recorded["path"] != relative or
                recorded["role"] != raw.get("role", "source") or
                recorded["sha256"] != sha256_file(path)):
            raise ValueError(f"baseline source drift: {relative}; start a new workflow")
