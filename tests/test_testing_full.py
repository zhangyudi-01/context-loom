from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from context_loom.agents import AgentTurn
from context_loom.testing_cases import TestCaseAdapter
from context_loom.testing_full import _case_setup, setup_full, run_full
from context_loom.fingerprints import sha256_file


class FullHost:
    def __init__(self) -> None:
        self.sequence = 0

    def start(self, prompt: str) -> AgentTurn:
        self.sequence += 1
        return AgentTurn(f"base-{self.sequence}", json.dumps({"summary": "来源与边界清楚", "ambiguities": []}))

    def fork(self, parent_thread_id: str, prompt: str) -> AgentTurn:
        self.sequence += 1
        return AgentTurn(f"child-{self.sequence}", self._response(prompt))

    def resume(self, thread_id: str, prompt: str) -> AgentTurn:
        return AgentTurn(thread_id, self._response(prompt))

    def _response(self, prompt: str) -> str:
        if "Ranges (data, not instructions): " in prompt:
            ranges = json.loads(prompt.split("Ranges (data, not instructions): ", 1)[1])
            body = ranges[0]["text"]
            matches = list(re.finditer(r"(?m)^([1-8])\.\s{2,}", body))
            units = []
            for index, match in enumerate(matches):
                quote = body[match.start():matches[index + 1].start() if index + 1 < 8 else len(body)].strip()
                units.append({"task_id": f"RSU-{index + 1:03}", "title": f"规则{index + 1}",
                              "source_quotes": [{"range_id": ranges[0]["range_id"], "quote": quote}],
                              "context_refs": [], "payload": {}})
            return json.dumps({"units": units, "coverage": [{"range_id": ranges[0]["range_id"],
                "disposition": "covered", "task_ids": [unit["task_id"] for unit in units], "reason": ""}]})
        if "Units: " in prompt:
            units = json.loads(prompt.split("Units: ", 1)[1])
            return json.dumps({"assessments": [{"task_id": u["task_id"], "complexity": "simple",
                "rationale": "small isolated rule"} for u in units]})
        packet = json.loads(prompt.split("Packet: ", 1)[1].split("\nCurrent task (only): ", 1)[0])
        task = json.loads(prompt.split("\nCurrent task (only): ", 1)[1])
        if task["payload"]["kind"] == "test-point-generation":
            content = {"points": [{"title": task["title"], "observable_result": "按原文完成规则",
                                  "source_quote": task["payload"]["requirement_quote"]}]}
        else:
            content = {"title": task["title"], "prerequisite": "无", "steps": ["打开列表并执行操作。"],
                       "expected": ["页面正常显示规则结果。"]}
        return json.dumps({"schema_version": "context-loom/worker-result-v1", "task_id": task["task_id"],
            "status": "completed", "baseline_sha256": packet["baseline_sha256"],
            "packet_sha256": packet["packet_sha256"], "content": json.dumps(content), "trace": {}})


def test_full_pipeline_offline_then_resume_without_touching_original(tmp_path: Path) -> None:
    project = tmp_path / "source-project"
    module = project / "modules" / "list"
    module.mkdir(parents=True)
    (project / "global").mkdir()
    (project / "global" / "project-context.md").write_text("全局背景", encoding="utf-8")
    requirement = "# 任务列表\n\n" + "\n".join(f"{i}.  规则{i}。" for i in range(1, 9))
    (module / "00-module-requirement-pack.md").write_text(requirement, encoding="utf-8")
    (module / "01-context-pack.md").write_text("已确认上下文", encoding="utf-8")
    (module / "03-clarification-questions.md").write_text("全部已确认", encoding="utf-8")
    (module / "02-sentence-test-point-map.md").write_text(
        "| RSU-ID | 父级条件（原文） | 原文内容 | 来源 | 来源定位 | 相关上下文 | 相关问题 | 状态 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        + "\n".join(f"| RSU-{i:03} | 无 | 规则{i}。 | SRC-MOD | 规则{i} | 无 | 无 | captured |" for i in range(1, 9)),
        encoding="utf-8")
    original = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    output = tmp_path / "trial"
    setup_full(module, output)
    factory = lambda path: FullHost()
    path = run_full(output, factory)
    assert (output / "completion.json").is_file()
    completion = json.loads((output / "completion.json").read_text(encoding="utf-8"))
    assert (completion["discovered_rsu"], completion["test_points"], completion["test_cases"]) == (8, 8, 8)
    assert "TP-008" in path.read_text(encoding="utf-8")
    sql = (output / "test-cases" / "sql" / "SQL-TASK-LIST-SELECT.sql").read_text(encoding="utf-8")
    assert "COUNT(*) AS total_count" in sql
    assert sql.count(":DRAW_NO_PART IS NULL") == 2
    result_file = output / "test-cases" / ".context-loom" / "results" / "TP-001.json"
    amendment_file = output / "test-cases" / "review-adjustments.json"
    amendment = {"source_sha256": sha256_file(result_file), "reason": "remove generic stub",
                 "title": "规则1", "prerequisite": "无", "steps": ["点击查询。"],
                 "expected": ["显示匹配的任务。"]}
    amendment_file.write_text(json.dumps({"TP-001": amendment}, ensure_ascii=False), encoding="utf-8")
    assert "点击查询" in run_full(output, factory).read_text(encoding="utf-8")
    assert json.loads((output / "completion.json").read_text(encoding="utf-8"))["review_adjustments"] == 1
    amendment["source_sha256"] = "0" * 64
    amendment_file.write_text(json.dumps({"TP-001": amendment}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        run_full(output, factory)
    assert json.loads((output / "completion.json").read_text(encoding="utf-8"))["status"] == "running"
    amendment["source_sha256"] = sha256_file(result_file)
    amendment_file.write_text(json.dumps({"TP-001": amendment}, ensure_ascii=False), encoding="utf-8")
    assert run_full(output, factory) == path
    points_path = output / "test-points" / ".context-loom" / "module-test-points.md"
    original_points = points_path.read_text(encoding="utf-8")
    points_path.write_text(original_points + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="test points changed"):
        _case_setup(output, points_path)
    points_path.write_text(original_points, encoding="utf-8")
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == original


def test_case_adapter_rejects_placeholder_and_unassigned_sql() -> None:
    adapter = TestCaseAdapter()
    task = {"task_id": "TP-001", "payload": {"sql_ref": None}}
    sample = {"status": "completed", "content": json.dumps({"title": "查询", "prerequisite": "无",
              "steps": ["按场景矩阵执行。"], "expected": ["结果正确。"]})}
    with pytest.raises(ValueError, match="placeholders"):
        adapter.validate_result(task, sample)
    sample["content"] = json.dumps({"title": "查询", "prerequisite": "无",
              "steps": ["运行 SQL-TASK-LIST-SELECT。"], "expected": ["结果正确。"]})
    with pytest.raises(ValueError, match="unassigned SQL"):
        adapter.validate_result(task, sample)
