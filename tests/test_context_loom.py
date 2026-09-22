from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from context_loom.assembly import assemble
from context_loom.baseline import compile_baseline
from context_loom.execution import prepare_next, submit_result
from context_loom.planning import build_plan
from context_loom.state import load_or_create


def workflow(tmp_path: Path) -> tuple[Path, dict]:
    (tmp_path / "context.md").write_text("shared context\n", encoding="utf-8")
    (tmp_path / "spec.md").write_text("authoritative requirement\n", encoding="utf-8")
    config = {
        "schema_version": "context-loom/workflow-v1",
        "workflow_id": "test-workflow",
        "root": ".",
        "sources": [
            {"source_id": "CONTEXT", "path": "context.md", "role": "context"},
            {"source_id": "SPEC", "path": "spec.md", "role": "spec"},
        ],
        "tasks": [
            {"task_id": "TASK-001", "title": "simple one", "complexity": "simple"},
            {"task_id": "TASK-002", "title": "complex two", "complexity": "complex"},
            {"task_id": "TASK-003", "title": "simple three", "complexity": "simple"},
        ],
    }
    (tmp_path / "context-loom.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path, config


def result(packet: dict, task_id: str, content: str) -> dict:
    return {
        "schema_version": "context-loom/worker-result-v1",
        "task_id": task_id,
        "status": "completed",
        "baseline_sha256": packet["baseline_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "content": content,
        "trace": {"task_id": task_id},
    }


def test_lifecycle_routes_and_assembles_in_task_order(tmp_path: Path) -> None:
    directory, config = workflow(tmp_path)
    baseline = compile_baseline(directory, config).to_dict()
    plan = build_plan(directory, config, baseline)
    assert [batch["mode"] for batch in plan["batches"]] == ["simple", "dedicated-fork", "simple"]

    packet = prepare_next(directory, config, baseline, plan)
    assert packet and packet["batch_id"] == "BATCH-001"
    for task in packet["tasks"]:
        submit_result(directory, config, result(packet, task["task_id"], task["title"]))

    packet = prepare_next(directory, config, baseline, plan)
    assert packet and packet["mode"] == "dedicated-fork"
    submit_result(directory, config, result(packet, "TASK-002", "complex result"))
    packet = prepare_next(directory, config, baseline, plan)
    assert packet and packet["batch_id"] == "BATCH-003"
    submit_result(directory, config, result(packet, "TASK-003", "last result"))
    output = assemble(directory, config, plan)
    text = output.read_text(encoding="utf-8")
    assert text.index("TASK-001") < text.index("TASK-002") < text.index("TASK-003")
    assert load_or_create(directory, config["workflow_id"])["assembly"]["status"] == "validated"


def test_result_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    directory, config = workflow(tmp_path)
    baseline = compile_baseline(directory, config).to_dict()
    plan = build_plan(directory, config, baseline)
    packet = prepare_next(directory, config, baseline, plan)
    bad = result(packet, "TASK-001", "bad")
    bad["packet_sha256"] = "wrong"
    try:
        submit_result(directory, config, bad)
    except ValueError as exc:
        assert "packet_sha256" in str(exc)
    else:
        raise AssertionError("hash mismatch should be rejected")


def test_simple_tasks_with_different_contexts_do_not_share_a_batch(tmp_path: Path) -> None:
    directory, config = workflow(tmp_path)
    config["tasks"] = [
        {"task_id": "TASK-001", "title": "same context one", "complexity": "simple", "source_refs": ["SPEC"]},
        {"task_id": "TASK-002", "title": "different context", "complexity": "simple", "source_refs": ["CONTEXT"]},
        {"task_id": "TASK-003", "title": "same context two", "complexity": "simple", "source_refs": ["SPEC"]},
    ]
    baseline = compile_baseline(directory, config).to_dict()
    plan = build_plan(directory, config, baseline)
    assert [batch["task_ids"] for batch in plan["batches"]] == [["TASK-001"], ["TASK-002"], ["TASK-003"]]
