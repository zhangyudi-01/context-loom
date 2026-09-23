"""Source-quoted pilot adapter; not a replacement for production testing runners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_json, write_text_atomic


class TestPointAdapter:
    def validate_result(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        if result.get("status") != "completed":
            return
        try:
            content = json.loads(result["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{task['task_id']}: content must be a JSON string of test points") from exc
        points = content.get("points") if isinstance(content, dict) else None
        if not isinstance(points, list) or not points:
            raise ValueError(f"{task['task_id']}: points must be a nonempty list")
        titles = set()
        for point in points:
            if not isinstance(point, dict) or any(not isinstance(point.get(k), str) or not point[k].strip()
                    for k in ("title", "observable_result", "source_quote")):
                raise ValueError(f"{task['task_id']}: each point needs title, observable_result and source_quote")
            if point["source_quote"] != task["payload"]["requirement_quote"]:
                raise ValueError(f"{task['task_id']}: source_quote differs from the literal RSU contract")
            if point["title"].strip() in titles:
                raise ValueError(f"{task['task_id']}: duplicate test-point title")
            titles.add(point["title"].strip())

    def finalize(self, workflow_dir: Path, assembled_markdown: Path) -> Path:
        from .config import load_config
        config = load_config(workflow_dir)
        output = ["# 隔离测试点试运行", "", "> 仅覆盖所选 RSU；需人工审阅，不替代原项目正式测试点。", "",
                  "| TP-ID | RSU-ID | 测试点 | 可观察结果 | 原文引述 |", "|---|---|---|---|---|"]
        number = 1
        for task in config["tasks"]:
            result = read_json(workflow_dir / ".context-loom" / "results" / f"{task['task_id']}.json")
            self.validate_result(task, result)
            for point in json.loads(result["content"])["points"]:
                def clean(value: str) -> str:
                    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()
                output.append(f"| TP-{number:03} | {task['task_id']} | {clean(point['title'])} | "
                              f"{clean(point['observable_result'])} | {clean(point['source_quote'])} |")
                number += 1
        path = workflow_dir / ".context-loom" / "module-test-points.md"
        write_text_atomic(path, "\n".join(output) + "\n")
        return path
