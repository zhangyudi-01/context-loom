"""Isolated end-to-end testing pilot: fresh RSU discovery, points, then cases.

The original module is immutable input. All generated content, context snapshots,
agent ledgers and SQL live under the caller's dedicated trial directory.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from .agents import AgentHost
from .baseline import assert_baseline_current, compile_baseline
from .config import load_config
from .discovery import discover_units, source_ranges, validate_stored_discovery
from .fingerprints import sha256_file, sha256_json
from .io import read_json, write_json_atomic, write_text_atomic
from .orchestrator import _baseline_session, run
from .testing_cases import TestCaseAdapter
from .testing_points import TestPointAdapter
from .testing_setup import setup_test_points


_REQUIRED = ("00-module-requirement-pack.md", "01-context-pack.md",
             "02-sentence-test-point-map.md", "03-clarification-questions.md")
_SQL = """-- SQL-TASK-LIST-SELECT: shared read-only task-list comparison.
-- Bind :DRAW_YEAR, :DRAW_NO_PART, :STATUS_CODE as NULL to omit each filter.
-- Apply :PAGE_SIZE and :OFFSET only when comparing the displayed page.
SELECT id, draw_year, draw_no, status_code, create_time
FROM notary_audit_batch
WHERE (:DRAW_YEAR IS NULL OR draw_year = :DRAW_YEAR)
  AND (:DRAW_NO_PART IS NULL OR draw_no LIKE CONCAT('%', :DRAW_NO_PART, '%'))
  AND (:STATUS_CODE IS NULL OR status_code = :STATUS_CODE)
ORDER BY id DESC
LIMIT :PAGE_SIZE OFFSET :OFFSET;

-- Use the same optional filters when validating the unpaginated result total.
SELECT COUNT(*) AS total_count
FROM notary_audit_batch
WHERE (:DRAW_YEAR IS NULL OR draw_year = :DRAW_YEAR)
  AND (:DRAW_NO_PART IS NULL OR draw_no LIKE CONCAT('%', :DRAW_NO_PART, '%'))
  AND (:STATUS_CODE IS NULL OR status_code = :STATUS_CODE);
"""


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("\u00a0", "")


def _source_record(output: Path) -> dict[str, Any]:
    record = read_json(output / "provenance.json")
    module = Path(record["source_module"])
    for relative, digest in record["sha256"].items():
        path = Path(record["source_project"]) / relative if relative.startswith("global/") else module / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"original input changed since isolation: {path}")
    return record


def setup_full(module: Path, output: Path) -> Path:
    module, output = module.resolve(), output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    project = next((p for p in module.parents if (p / "global" / "project-context.md").is_file()), None)
    if project is None or not module.is_relative_to(project / "modules") or output.is_relative_to(project):
        raise ValueError("source must be a real module and trial directory must be outside its project")
    source_paths = {name: module / name for name in _REQUIRED}
    source_paths["global/project-context.md"] = project / "global" / "project-context.md"
    # Keep reference links inside snapshotted FC/DC cards resolvable after the
    # source module's deeper path is flattened into modules/task-list.
    linked = (
        "global/source-materials/current-requirement/开奖监督平台PRD文档.md",
        "global/source-materials/current-requirement/attachments/北单管理平台需求PRD文档.md",
        "global/source-materials/database-docs/北单公证-库表设计.md",
        "global/source-materials/database-docs/v2t数据库设计文档.md",
    )
    source_paths.update({relative: project / relative for relative in linked
                         if (project / relative).is_file()})
    for folder in ("context-cards", "data-closures"):
        for item in (module / folder).glob("*.md"):
            source_paths[f"{folder}/{item.name}"] = item
    if any(not path.is_file() for path in source_paths.values()):
        raise ValueError("missing required module preanalysis input")
    snapshot = output / "snapshot-project"
    target = snapshot / "modules" / "task-list"
    for relative, source in source_paths.items():
        destination = snapshot / relative if relative.startswith("global/") else target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if relative.startswith("global/"):
            # Existing relative links from the flattened original module
            # resolve to output/global, not snapshot-project/global.
            linked_destination = output / relative
            linked_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, linked_destination)
    # Preserve old analysis solely as a confirmed-context reference; discovery
    # cannot read or copy its RSU map as its generated output.
    old_map = target / "02-sentence-test-point-map.md"
    old_map.replace(output / "confirmed-reference-map.md")
    output.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output / "provenance.json", {
        "source_project": str(project), "source_module": str(module),
        "sha256": {relative: sha256_file(source) for relative, source in source_paths.items()},
        "status": "snapshot-only; no RSU or test point has been generated",
    })
    write_text_atomic(output / "README.md", "# Task-list end-to-end isolation trial\n\n"
        "This is a fresh RSU discovery, test-point generation and test-case generation run. "
        "The source module is read-only; confirmed context is a reference, not a generated result.\n"
        "Outputs appear in preanalysis/, test-points/, test-cases/ as each phase completes.\n")
    return output


def _reference_rows(output: Path) -> list[list[str]]:
    rows = []
    for line in (output / "confirmed-reference-map.md").read_text(encoding="utf-8").splitlines():
        fields = [item.strip() for item in line.strip().strip("|").split("|")]
        if len(fields) == 8 and re.fullmatch(r"RSU-\d{3,}", fields[0]):
            rows.append(fields)
    return rows


def _match_reference(quote: str, rows: list[list[str]]) -> list[str] | None:
    # Human-confirmed cards clarify the contract, but do not determine the
    # newly discovered RSU count or quote boundaries.
    norm = _normalized(quote)
    matching = [row for row in rows if _normalized(row[2]) in norm or norm in _normalized(row[2])]
    return max(matching, key=lambda row: len(_normalized(row[2])), default=None)


def _verify_rules(requirement: str, units: list[dict[str, Any]]) -> None:
    rules = list(re.finditer(r"(?m)^([1-8])\.\s{2,}", requirement))
    if len(rules) != 8:
        raise ValueError("expected eight top-level task-list business rules in requirement snapshot")
    quotes = [_normalized(part["quote"]) for unit in units for part in unit["payload"]["source_quotes"]]
    for index, found in enumerate(rules):
        segment = _normalized(requirement[found.start():rules[index + 1].start() if index + 1 < 8 else len(requirement)])
        if not any(quote in segment and len(quote) >= 4 for quote in quotes):
            raise ValueError(f"discovery left business rule {index + 1} uncovered")


def _preanalysis(output: Path, host: AgentHost) -> Path:
    directory = output / "preanalysis"
    module = output / "snapshot-project" / "modules" / "task-list"
    config_file = directory / "context-loom.json"
    if not config_file.is_file():
        config = {
            "schema_version": "context-loom/workflow-v1", "workflow_id": "task-list-preanalysis",
            "root": str(output / "snapshot-project"),
            "sources": [
                {"source_id": "SRC-GLOBAL", "path": "global/project-context.md", "role": "context"},
                {"source_id": "SRC-MOD", "path": "modules/task-list/00-module-requirement-pack.md", "role": "requirement"},
                {"source_id": "CTX-CONFIRMED", "path": "modules/task-list/01-context-pack.md", "role": "context"},
                {"source_id": "Q-CONFIRMED", "path": "modules/task-list/03-clarification-questions.md", "role": "context"},
            ],
            "task_discovery": {"source_ids": ["SRC-MOD"], "id_prefix": "RSU",
                "guidance": "Testing preanalysis: an RSU is one semantically complete requirement contract. "
                "Do not turn the prototype image or structural headings into an RSU. "
                "Split the three independent filter controls and three state-dependent row actions; "
                "keep query result, ordering, pagination and its five fields together as ONE composite RSU. "
                "Cover all eight numbered business rules. Keep source_quotes verbatim, without rewriting."},
        }
        write_json_atomic(config_file, config)
    config = load_config(directory)
    baseline_file = directory / ".context-loom" / "baseline.json"
    baseline = read_json(baseline_file) if baseline_file.is_file() else compile_baseline(directory, config).to_dict()
    assert_baseline_current(directory, config, baseline)
    thread_id = _baseline_session(directory, config, baseline, host)
    discovery_file = directory / ".context-loom" / "discovery.json"
    if discovery_file.exists():
        discovery = read_json(discovery_file)
        if discovery["range_sha256"] != sha256_json(source_ranges(directory, config)):
            raise ValueError("discovery inputs changed")
        units = validate_stored_discovery(discovery, source_ranges(directory, config), "RSU")
    else:
        units = discover_units(directory, config, host, thread_id)
    requirement = (module / "00-module-requirement-pack.md").read_text(encoding="utf-8")
    _verify_rules(requirement, units)
    reference = _reference_rows(output)
    def cell(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().replace("|", "\\|")
    mapping = ["# 任务列表：重新生成的 RSU 原文映射", "", "来源：本次需求快照；人工确认资料仅补充上下文。", "",
               "| RSU-ID | 父级条件（原文） | 原文内容 | 来源 | 来源定位 | 相关上下文 | 相关问题 | 状态 |",
               "|---|---|---|---|---|---|---|---|"]
    for unit in units:
        quote = " ".join(part["quote"].strip() for part in unit["payload"]["source_quotes"])
        match = _match_reference(quote, reference)
        # Long composite quotes may contain line breaks. Flatten whitespace, then
        # check the normalized text against the immutable requirement snapshot.
        if _normalized(quote) not in _normalized(requirement):
            raise ValueError(f"discovered quote is not a contiguous requirement excerpt: {unit['task_id']}")
        mapping.append("| " + " | ".join([
            unit["task_id"], cell(match[1]) if match else "无", cell(quote), "SRC-MOD",
            cell(match[4]) if match else cell(unit["title"]),
            cell(match[5]) if match else "无", cell(match[6]) if match else "无", "captured",
        ]) + " |")
    write_text_atomic(module / "02-sentence-test-point-map.md", "\n".join(mapping) + "\n")
    summary = read_json(directory / ".context-loom" / "session.json")["summary"]
    write_text_atomic(directory / "01-generated-analysis.md", "# 本次前置分析\n\n" + summary + "\n\n"
                      "## 来源与确认边界\n\nRSU 从当前模块原文重新发现。详情、权限、状态和数据约束采用原模块已确认"
                      "的 Context Pack、Q/FC/DC 作为只读上下文；不将确认结论伪作 PRD 原文。\n\n"
                      f"已覆盖 {len(units)} 个 RSU；8 条顶层业务规则均有原文引述。\n")
    write_json_atomic(directory / "completion.json", {"status": "preanalysis-complete",
                       "discovered_rsu": len(units), "mapping_sha256": sha256_file(module / "02-sentence-test-point-map.md")})
    return module / "02-sentence-test-point-map.md"


def _case_setup(output: Path, points_path: Path) -> Path:
    directory = output / "test-cases"
    config_file = directory / "context-loom.json"
    snapshot_points = output / "snapshot-project" / "modules" / "task-list" / "04-generated-test-points.md"
    if config_file.exists():
        if not snapshot_points.is_file() or sha256_file(snapshot_points) != sha256_file(points_path):
            raise ValueError("test points changed since test-case setup; start a new isolated trial")
        return config_file
    module = output / "snapshot-project" / "modules" / "task-list"
    shutil.copy2(points_path, snapshot_points)
    point_config = load_config(output / "test-points")
    by_rsu = {t["task_id"]: t for t in point_config["tasks"]}
    rows = []
    for line in points_path.read_text(encoding="utf-8").splitlines():
        fields = [item.strip().replace("\\|", "|") for item in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(fields) == 5 and re.fullmatch(r"TP-\d{3,}", fields[0]):
            rows.append(fields)
    if not rows or len(set(row[0] for row in rows)) != len(rows):
        raise ValueError("generated points are absent or duplicated")
    sql_path = directory / "sql" / "SQL-TASK-LIST-SELECT.sql"
    tasks = []
    for tp_id, rsu_id, title, observable, quote in rows:
        parent = by_rsu[rsu_id]
        # A shared SELECT only for query/list data; UI controls and navigation
        # never get SQL merely because they reference a database context card.
        use_sql = bool(re.search(r"筛选|模糊匹配|排序|分页|结果字段|列值|任务列表查询", title)) and not bool(
            re.search(r"选项|默认|输入|按钮|重置|跳转|弹窗|单选", title))
        tasks.append({"task_id": tp_id, "title": title,
            "source_refs": ["SRC-GLOBAL", "SRC-MOD", "CTX", "SRC-TP"],
            "context_refs": parent["context_refs"],
            "payload": {"kind": "test-case-generation", "rsu_id": rsu_id, "point": title,
                "observable_result": observable, "source_quote": quote,
                "sql_ref": "SQL-TASK-LIST-SELECT.sql" if use_sql else None,
                "instructions": "Write ONE concise, executable test case for this point only. "
                "content must be JSON {title:string,prerequisite:string,steps:[string],expected:[string]}. "
                "Use prerequisite '无' when unnecessary. Give actual conditions and operations, not references "
                "to a TP, a scenario matrix or a data-closure plan. One step maps to one expected item. "
                "Do not expand other points or modules. Keep simple actions one sentence. "
                "Use execution-time year Y and Y-1 for relative-year rules, not a fixed sample year. "
                "Choose the smallest data set needed to demonstrate a boundary; selecting a page-size "
                "option does not require filling that many rows. "
                "When the source says '详见后续章节', verify only this list entry and its destination; "
                "do not send requests to the destination module's business API or assert its business result. "
                "If and only if sql_ref is present and database data comparison is needed, reference "
                "the shared SQL file in one step, and state simply that page results match the SQL result. "
                "Do not invent SQL or require SQL for UI-only observations."}})
    config = {"schema_version": "context-loom/workflow-v1", "workflow_id": "task-list-cases",
        "domain": "testing-test-cases", "root": str(output / "snapshot-project"),
        "sources": [
            {"source_id": "SRC-GLOBAL", "path": "global/project-context.md", "role": "context"},
            {"source_id": "SRC-MOD", "path": "modules/task-list/00-module-requirement-pack.md", "role": "requirement"},
            {"source_id": "CTX", "path": "modules/task-list/01-context-pack.md", "role": "context"},
            {"source_id": "SRC-TP", "path": "modules/task-list/04-generated-test-points.md", "role": "context"}],
        "contexts": point_config["contexts"], "tasks": tasks,
        "policy": {"max_simple_batch_size": 8}}
    write_json_atomic(config_file, config)
    write_text_atomic(sql_path, _SQL)
    write_text_atomic(directory / "README.md", "# 重新生成的测试用例\n\n"
                      "共用查询：sql/SQL-TASK-LIST-SELECT.sql；仅适用列表数据比较，"
                      "并非所有测试点都需要数据库查询。SQL 是静态模板，尚未对测试库执行 EXPLAIN。\n")
    return config_file


def run_full(output: Path, host_factory: Any) -> Path:
    """Resume each phase from JSON checkpoints; never infer progress from logs."""
    output = output.resolve()
    _source_record(output)
    write_json_atomic(output / "completion.json", {"status": "running"})
    _preanalysis(output, host_factory(output / "preanalysis"))
    _source_record(output)
    module = output / "snapshot-project" / "modules" / "task-list"
    point_dir = output / "test-points"
    if not (point_dir / "context-loom.json").is_file():
        discovered = read_json(output / "preanalysis" / ".context-loom" / "discovery.json")["units"]
        setup_test_points(module, point_dir, [unit["task_id"] for unit in discovered])
        write_text_atomic(point_dir / "README.md", "# 全模块测试点隔离试运行\n\n"
                          "本次选中了新发现的全部 RSU；测试点保存在 .context-loom/module-test-points.md。"
                          "输入来源于只读快照，不覆盖源模块；完整性与可执行性仍需审阅。\n")
    points_path = run(point_dir, load_config(point_dir), host_factory(point_dir), TestPointAdapter())
    _source_record(output)
    _case_setup(output, points_path)
    case_dir = output / "test-cases"
    cases_path = run(case_dir, load_config(case_dir), host_factory(case_dir), TestCaseAdapter())
    _source_record(output)
    findings = []
    amendments_file = case_dir / "review-adjustments.json"
    amendments = read_json(amendments_file) if amendments_file.is_file() else {}
    for task in load_config(case_dir)["tasks"]:
        case = TestCaseAdapter().reviewed_data(case_dir, task, amendments)
        prose = " ".join([case["prerequisite"], *case["steps"], *case["expected"]])
        quote = task["payload"]["source_quote"]
        if re.search(r"20\d{2}年", prose) and not re.search(r"20\d{2}年", quote):
            findings.append({"tp_id": task["task_id"], "kind": "fixed-year",
                             "note": "相对年份规则写成了固定日历年；执行时应改为 Y / Y-1。"})
        if "详见后续章节" in quote and re.search(r"(直接向|绕过页面).{0,25}接口", prose):
            findings.append({"tp_id": task["task_id"], "kind": "cross-module-api",
                             "note": "列表入口用例扩展到了目标模块的接口提交，应只测当前列表入口。"})
        if "分页大小" in task["title"] and re.search(r"至少\s*20[01]\s*条", case["prerequisite"]):
            findings.append({"tp_id": task["task_id"], "kind": "heavy-fixture",
                             "note": "为检查分页选项准备 200 多条任务成本过高；只为真实跨页边界准备最小数据。"})
    write_json_atomic(output / "quality-review.json", {"status": "needs-human-review" if findings else "heuristics-clear",
                       "findings": findings, "sql_database_verified": False})
    write_json_atomic(output / "completion.json", {
        "status": "pipeline-complete", "discovered_rsu": len(read_json(output / "preanalysis" / ".context-loom" / "discovery.json")["units"]),
        "test_points": sum(1 for line in points_path.read_text(encoding="utf-8").splitlines()
                           if re.match(r"\| TP-\d{3,} \|", line)),
        "test_cases": sum(1 for line in cases_path.read_text(encoding="utf-8").splitlines() if re.match(r"\| \d+ \| TP-", line)),
        "points_sha256": sha256_file(points_path), "cases_sha256": sha256_file(cases_path),
        "quality_findings": len(findings), "quality_review": "quality-review.json",
        "review_adjustments": len(amendments),
    })
    return cases_path
