from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from context_loom.agents import AgentTurn
from context_loom.config import load_config
from context_loom.orchestrator import run
from context_loom.testing_points import TestPointAdapter
from context_loom.testing_setup import setup_test_points


def fixture(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "source-project"
    module = project / "modules" / "task-list"
    module.mkdir(parents=True)
    (project / "global").mkdir()
    (project / "global" / "project-context.md").write_text("共享背景", encoding="utf-8")
    (module / "00-module-requirement-pack.md").write_text("彩票年只能选择当前年。\n奖期输入仅限数字。", encoding="utf-8")
    (module / "01-context-pack.md").write_text("任务列表模块", encoding="utf-8")
    (module / "02-sentence-test-point-map.md").write_text(
        "| RSU-ID | 父级条件（原文） | 原文内容 | 来源 | 来源定位 | 相关上下文 | 相关问题 | 状态 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| RSU-001 | 查询 | 彩票年只能选择当前年。 | SRC-MOD | 查询 1.1 | DC-001 | 无 | captured |\n"
        "| RSU-002 | 查询 | 奖期输入仅限数字。 | SRC-MOD | 查询 1.2 | DC-001 | 无 | captured |\n", encoding="utf-8")
    (module / "data-closures").mkdir()
    (module / "data-closures" / "DC-001-查询.md").write_text("查询数据闭包", encoding="utf-8")
    return project, module


class FakeHost:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.serial = 0

    def start(self, prompt: str) -> AgentTurn:
        self.calls.append(("start", ""))
        return AgentTurn("base", json.dumps({"summary": "任务列表", "ambiguities": []}))

    def fork(self, parent_thread_id: str, prompt: str) -> AgentTurn:
        self.serial += 1
        self.calls.append(("fork", parent_thread_id))
        return AgentTurn(f"child-{self.serial}", self._answer(prompt))

    def resume(self, thread_id: str, prompt: str) -> AgentTurn:
        self.calls.append(("resume", thread_id))
        return AgentTurn(thread_id, self._answer(prompt))

    def _answer(self, prompt: str) -> str:
        if "Units: " in prompt:
            units = json.loads(prompt.split("Units: ", 1)[1])
            return json.dumps({"assessments": [{"task_id": u["task_id"], "complexity": "simple",
                "rationale": "independent query"} for u in units]})
        packet = json.loads(prompt.split("Packet: ", 1)[1].split("\nCurrent task (only): ", 1)[0])
        task = json.loads(prompt.split("\nCurrent task (only): ", 1)[1])
        content = {"points": [{"title": task["task_id"] + " 可用", "observable_result": "结果符合原文",
                               "source_quote": task["payload"]["requirement_quote"]}]}
        return json.dumps({"schema_version": "context-loom/worker-result-v1", "task_id": task["task_id"],
                           "status": "completed", "baseline_sha256": packet["baseline_sha256"],
                           "packet_sha256": packet["packet_sha256"], "content": json.dumps(content), "trace": {}})


def test_setup_and_offline_run_do_not_touch_original_project(tmp_path: Path) -> None:
    project, module = fixture(tmp_path)
    original = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    output = tmp_path / "pilot"
    setup_test_points(module, output, ["RSU-001", "RSU-002"])
    config = load_config(output)
    assert config["root"] == str(project)
    assert [t["task_id"] for t in config["tasks"]] == ["RSU-001", "RSU-002"]
    assert config["contexts"][0]["context_id"] == "DC-001"
    fake = FakeHost()
    artifact = run(output, config, fake, TestPointAdapter())
    assert "RSU-002" in artifact.read_text(encoding="utf-8")
    assert (output / ".context-loom" / "trace.json").is_file()
    assert fake.calls == [("start", ""), ("fork", "base"), ("fork", "base"), ("resume", "child-2")]
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == original


def test_rejects_unknown_and_tampered_rsu_without_creating_directory(tmp_path: Path) -> None:
    _, module = fixture(tmp_path)
    with pytest.raises(ValueError, match="RSU not found"):
        setup_test_points(module, tmp_path / "bad", ["RSU-999"])
    assert not (tmp_path / "bad").exists()
    data = (module / "00-module-requirement-pack.md")
    data.write_text("unrelated", encoding="utf-8")
    with pytest.raises(ValueError, match="literal module requirement"):
        setup_test_points(module, tmp_path / "bad", ["RSU-001"])


def test_test_point_adapter_rejects_fabricated_quote() -> None:
    adapter = TestPointAdapter()
    with pytest.raises(ValueError, match="differs from the literal"):
        adapter.validate_result({"task_id": "RSU-001", "payload": {"requirement_quote": "true"}},
            {"status": "completed", "content": json.dumps({"points": [{"title": "t",
                "observable_result": "o", "source_quote": "fake"}]})})
