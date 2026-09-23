"""Create a source-backed testing pilot without copying the original project's files."""

from __future__ import annotations

import re
from pathlib import Path

from .io import write_json_atomic, write_text_atomic


RSU_ID = re.compile(r"RSU-\d{3,}")


def setup_test_points(module_dir: Path, output_dir: Path, rsu_ids: list[str]) -> Path:
    module_dir, output_dir = module_dir.resolve(), output_dir.resolve()
    if not rsu_ids or len(set(rsu_ids)) != len(rsu_ids) or any(not RSU_ID.fullmatch(r) for r in rsu_ids):
        raise ValueError("provide distinct RSU IDs, e.g. --rsu RSU-001 RSU-002")
    if output_dir.exists():
        raise ValueError(f"output already exists; choose a new isolated directory: {output_dir}")
    project = next((p for p in module_dir.parents if (p / "global" / "project-context.md").is_file()), None)
    if project is None or not module_dir.is_relative_to(project / "modules"):
        raise ValueError("module must be under a project with global/project-context.md and modules/")
    if output_dir.is_relative_to(project):
        raise ValueError("output must be outside the existing project to keep its sources and outputs untouched")
    required = ["00-module-requirement-pack.md", "01-context-pack.md", "02-sentence-test-point-map.md"]
    for filename in required:
        if not (module_dir / filename).is_file():
            raise ValueError(f"missing preanalysis input: {module_dir / filename}")
    requirement = (module_dir / required[0]).read_text(encoding="utf-8")
    mapping = (module_dir / required[2]).read_text(encoding="utf-8")
    rows = {}
    for line in mapping.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 8 and RSU_ID.fullmatch(cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate RSU mapping: {cells[0]}")
            rows[cells[0]] = cells
    selected = []
    for rsu_id in rsu_ids:
        if rsu_id not in rows:
            raise ValueError(f"RSU not found in the original mapping: {rsu_id}")
        row = rows[rsu_id]
        if (row[3] != "SRC-MOD" or
                re.sub(r"\s+", "", row[2]) not in re.sub(r"\s+", "", requirement) or
                row[7] != "captured"):
            raise ValueError(f"RSU lacks a captured, literal module requirement: {rsu_id}")
        selected.append(row)
    module_rel = module_dir.relative_to(project)

    def source_path(filename: str) -> str:
        return (module_rel / filename).as_posix()

    contexts = []
    seen_contexts = set()
    tasks = []
    for row in selected:
        rsu_id, parent, quote, _, location, related, questions, _ = row
        context_refs = []
        for ref in re.findall(r"(?:FC|DC)-\d{3}", related):
            folder = "context-cards" if ref.startswith("FC-") else "data-closures"
            matches = list((module_dir / folder).glob(ref + "-*.md"))
            if len(matches) != 1:
                raise ValueError(f"expected exactly one dynamic context for {rsu_id}: {ref}")
            if ref not in seen_contexts:
                contexts.append({"context_id": ref, "path": source_path(str(matches[0].relative_to(module_dir)))})
                seen_contexts.add(ref)
            context_refs.append(ref)
        if questions != "无":
            filename = "03-clarification-questions.md"
            if not (module_dir / filename).is_file():
                raise ValueError(f"missing clarification resource: {filename}")
            if "CLARIFICATIONS" not in seen_contexts:
                contexts.append({"context_id": "CLARIFICATIONS", "path": source_path(filename)})
                seen_contexts.add("CLARIFICATIONS")
            context_refs.append("CLARIFICATIONS")
        tasks.append({
            "task_id": rsu_id,
            "title": f"测试点：{location}",
            "source_refs": ["SRC-GLOBAL", "SRC-MOD", "CTX"],
            "context_refs": context_refs,
            "payload": {
                "kind": "test-point-generation", "source_location": location,
                "parent_requirement": parent, "requirement_quote": quote,
                "question_refs": questions,
                "instructions": (
                    "只针对当前 RSU 生成必要的、各自可独立判定的测试点，避免同义重复和跨模块扩展。"
                    "content 必须是 JSON 字符串，内容结构为 {\"points\":[{\"title\":\"...\","
                    "\"observable_result\":\"...\",\"source_quote\":\"原文完整引述\"}]}。"
                    "每条 source_quote 使用本任务 requirement_quote 原文；不得编造缺失业务规则。"
                    "若原文只是跳转或动作入口并写有‘详见后续章节’，只验证当前列表的入口与去向，"
                    "不要把目标模块的业务提交、接口绕行或跨模块处理扩展为本模块测试点。"
                ),
            },
        })
    config = {
        "schema_version": "context-loom/workflow-v1",
        "workflow_id": "testing-" + "-".join(r.lower() for r in rsu_ids),
        "domain": "testing-test-points", "root": str(project),
        "sources": [
            {"source_id": "SRC-GLOBAL", "path": "global/project-context.md", "role": "context"},
            {"source_id": "SRC-MOD", "path": source_path(required[0]), "role": "requirement"},
            {"source_id": "CTX", "path": source_path(required[1]), "role": "module-context"},
        ],
        "contexts": contexts, "tasks": tasks, "policy": {"max_simple_batch_size": 5},
    }
    output_dir.mkdir(parents=True)
    write_json_atomic(output_dir / "context-loom.json", config)
    write_text_atomic(output_dir / "README.md", "# 隔离测试点试运行\n\n"
        "本目录只读引用项目原资料；生成结果与执行状态只会写入当前目录。"
        "本次仅覆盖配置中的 RSU，不是模块完整测试点。\n\n"
        "1. `context-loom doctor .` 检查输入和执行条件（无模型费用）。\n"
        "2. `context-loom compile .` 编译基线（无模型费用）。\n"
        "3. 确认费用后执行 `context-loom run .`，使用 Codex CLI 产生模型费用。\n"
        "4. 查看 `.context-loom/module-test-points.md` 和 `.context-loom/trace.json`。\n")
    return output_dir / "context-loom.json"
