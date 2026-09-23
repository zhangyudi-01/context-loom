"""A focused one-TP-per-case adapter for isolated testing workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .fingerprints import sha256_file
from .io import read_json, write_text_atomic


_PLACEHOLDERS = ("按场景矩阵", "按数据闭包执行计划", "执行当前 TP", "当前 TP 包含", "各来源场景")


class TestCaseAdapter:
    def reviewed_data(self, workflow_dir: Path, task: dict[str, Any],
                      amendments: dict[str, Any] | None = None) -> dict[str, Any]:
        result_file = workflow_dir / ".context-loom" / "results" / f"{task['task_id']}.json"
        result = read_json(result_file)
        self.validate_result(task, result)
        data = json.loads(result["content"])
        entry = (amendments or {}).get(task["task_id"])
        if entry is not None:
            if (not isinstance(entry, dict) or entry.get("source_sha256") != sha256_file(result_file)
                    or not isinstance(entry.get("reason"), str) or not entry["reason"].strip()):
                raise ValueError(f"{task['task_id']}: review amendment is stale or lacks a reason")
            if not all(key in entry for key in ("title", "prerequisite", "steps", "expected")):
                raise ValueError(f"{task['task_id']}: review amendment is incomplete")
            data = {key: entry[key] for key in ("title", "prerequisite", "steps", "expected")}
            self.validate_result(task, {"status": "completed", "content": json.dumps(data, ensure_ascii=False)})
        return data

    def validate_result(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        if result.get("status") != "completed":
            return
        try:
            data = json.loads(result["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{task['task_id']}: test-case content must be JSON") from exc
        if not isinstance(data, dict) or not all(k in data for k in ("title", "prerequisite", "steps", "expected")):
            raise ValueError(f"{task['task_id']}: missing test-case fields")
        if not all(isinstance(data[k], str) and data[k].strip() for k in ("title", "prerequisite")):
            raise ValueError(f"{task['task_id']}: title and prerequisite must be nonempty")
        steps, expected = data["steps"], data["expected"]
        if (not isinstance(steps, list) or not steps or not isinstance(expected, list)
                or len(steps) != len(expected) or any(not isinstance(s, str) or not s.strip() for s in steps + expected)):
            raise ValueError(f"{task['task_id']}: each step needs exactly one expected result")
        prose = " ".join([data["title"], data["prerequisite"], *steps, *expected])
        if any(text in prose for text in _PLACEHOLDERS):
            raise ValueError(f"{task['task_id']}: execution placeholders are forbidden")
        if re.search(r"\b(?:TP|RSU|DC|DP)-\d{3,}\b", prose):
            raise ValueError(f"{task['task_id']}: internal IDs cannot appear in executable prose")
        if "SQL-TASK-LIST-SELECT" in prose and not task["payload"].get("sql_ref"):
            raise ValueError(f"{task['task_id']}: unassigned SQL must not be referenced")

    def finalize(self, workflow_dir: Path, assembled_markdown: Path) -> Path:
        from .config import load_config
        config = load_config(workflow_dir)
        amendments_file = workflow_dir / "review-adjustments.json"
        amendments = read_json(amendments_file) if amendments_file.is_file() else {}
        if not isinstance(amendments, dict) or set(amendments) - {t["task_id"] for t in config["tasks"]}:
            raise ValueError("review amendments refer to an unknown test point")
        rows = ["# 任务列表：隔离试运行测试用例", "", "> 基于本次重新生成的测试点；待测试人员审核，不覆盖正式用例。", "",
                "| 序号 | TP-ID | 用例名称 | 前置条件 | 步骤 | 预期结果 |",
                "|---|---|---|---|---|---|"]
        for number, task in enumerate(config["tasks"], 1):
            data = self.reviewed_data(workflow_dir, task, amendments)
            def clean(text: str) -> str:
                return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>").strip()
            steps = "<br>".join(f"{n}. {clean(text)}" for n, text in enumerate(data["steps"], 1))
            expected = "<br>".join(f"{n}. {clean(text)}" for n, text in enumerate(data["expected"], 1))
            rows.append(f"| {number} | {task['task_id']} | {clean(data['title'])} | "
                        f"{clean(data['prerequisite'])} | {steps} | {expected} |")
        target = workflow_dir / ".context-loom" / "module-test-cases.md"
        write_text_atomic(target, "\n".join(rows) + "\n")
        return target
