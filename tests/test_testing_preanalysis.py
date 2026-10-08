from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from context_loom.config import load_config
from context_loom.orchestrator import run
from context_loom.testing_points import TestPointAdapter
from context_loom.testing_preanalysis import load_preanalysis, refs, split_row
from context_loom.testing_setup import setup_test_points
from test_testing_pilot import FakeHost


def fixture(tmp_path: Path, context_path: str = "global/project-context.md", remap: bool = False) -> tuple[Path, Path]:
    project = tmp_path / "project"
    module = project / "modules" / "task-list"
    pre = module / "preanalysis"
    (pre / "context-cards").mkdir(parents=True)
    (pre / "data-closures").mkdir()
    context = project / context_path
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text("共享项目背景。", encoding="utf-8")
    roles = {"global_context": "SRC-PROJECT" if remap else "SRC-GLOBAL",
             "module_requirement": "SRC-REQUIREMENT" if remap else "SRC-MOD",
             "module_context": "SRC-CONTEXT" if remap else "CTX"}
    manifest = {"schema_version": "preanalysis/v1", "module_root": "..",
                "artifacts": {"readme": "README.md", "module_requirement": "00-module-requirement-pack.md",
                              "context_pack": "01-context-pack.md", "rsu_map": "02-sentence-test-point-map.md",
                              "clarifications": "03-clarification-questions.md",
                              "context_card_index": "context-cards/README.md"},
                "resource_roles": roles, "output": {"test_points_dir": "../test-points"}}
    (pre / "preanalysis-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pre / "README.md").write_text("# 分析索引", encoding="utf-8")
    (pre / "00-module-requirement-pack.md").write_text("# 查询\n彩票年只能选择当前年。\n奖期输入仅限数字。\n取值只能为 A | B。", encoding="utf-8")
    (pre / "01-context-pack.md").write_text("# 模块逻辑\n查询。", encoding="utf-8")
    (pre / "03-clarification-questions.md").write_text(
        "| Q-ID | 关联原文/上下文 | 状态 | 人工确认结论 | 回填结果 |\n"
        "|---|---|---|---|---|\n| Q-001 | RSU-001 | answered | 当前年使用浏览器年份 | 已回填 CTX |\n", encoding="utf-8")
    (pre / "context-cards" / "README.md").write_text("# Context Cards\n", encoding="utf-8")
    (pre / "context-cards" / "FC-001-查询.md").write_text("# FC-001 查询\n[依据](../unused.md)", encoding="utf-8")
    (pre / "unused.md").write_text("不应递归投喂的来源。", encoding="utf-8")
    (pre / "data-closures" / "DC-001-查询.md").write_text("# DC-001 查询\n只读数据闭包。", encoding="utf-8")
    (pre / "data-closures" / "README.md").write_text(
        "| DC-ID | 业务数据闭包 | 可点击文件 | 状态 | 关联 RSU | 来源资源 |\n"
        "|---|---|---|---|---|---|\n| DC-001 | 查询 | [闭包](DC-001-查询.md) | ready | RSU-001 | SRC-MOD |\n", encoding="utf-8")
    global_id, mod_id, ctx_id = (roles[key] for key in ("global_context", "module_requirement", "module_context"))
    mapping = (
        "| 资源 ID | 可点击文件 | 定位用途 |\n|---|---|---|\n"
        f"| {global_id} | [全局](../../../{context_path}) | 背景 |\n"
        f"| {mod_id} | [原文](00-module-requirement-pack.md) | 需求 |\n"
        f"| {ctx_id} | [逻辑](01-context-pack.md) | 上下文 |\n"
        "| Q-INDEX | [问题](03-clarification-questions.md) | 结论 |\n"
        "| FC-INDEX | [卡片索引](context-cards/README.md) | 索引 |\n"
        "| FC-001 | [卡片](context-cards/FC-001-查询.md) | 关联逻辑 |\n"
        "| DC-INDEX | [数据索引](data-closures/README.md) | 索引 |\n"
        "| DC-001 | [闭包](data-closures/DC-001-查询.md) | 查询 |\n"
        "| SRC-UNUSED | [其他资料](unused.md) | 证据而非任务输入 |\n"
        "| RSU-ID | 父级条件（原文） | 原文内容 | 来源 | 来源定位 | 相关上下文 | 相关问题 | 状态 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"| RSU-001 | 查询 | 彩票年只能选择当前年。 | {mod_id} | 查询 1 | {ctx_id}、FC-001、DC-001、RSU-002 | Q-001 | captured |\n"
        f"| RSU-002 | 查询 | 奖期输入仅限数字。 | {mod_id} | 查询 2 | {ctx_id} | 无 | captured |\n"
        f"| RSU-003 | 查询 | 取值只能为 A \\| B。 | {mod_id} | 查询 3 | {ctx_id} | 无 | captured |\n")
    (pre / "02-sentence-test-point-map.md").write_text(mapping, encoding="utf-8")
    return project, module


def replace(path: Path, before: str, after: str) -> None:
    content = path.read_text(encoding="utf-8")
    assert before in content
    path.write_text(content.replace(before, after), encoding="utf-8")


@pytest.mark.parametrize("context_path,remap", [("global/project-context.md", False),
    ("00-global/00-project-context.md", False), ("knowledge/custom-context.md", True)])
def test_canonical_setup_and_fake_run_keep_sources_unchanged(tmp_path: Path, context_path: str, remap: bool) -> None:
    project, module = fixture(tmp_path, context_path, remap)
    original = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    output = tmp_path / "pilot"
    setup_test_points(module, output, ["RSU-001", "RSU-003"])
    config = load_config(output)
    assert config["sources"][0]["path"] == context_path
    assert {c["context_id"] for c in config["contexts"]} == {"FC-001", "DC-001", "CLARIFICATIONS"}
    assert config["tasks"][0]["payload"]["supporting_rsu_rows"][0][0] == "RSU-002"
    assert config["tasks"][0]["payload"]["rsu_row"][0] == "RSU-001"
    assert config["tasks"][1]["context_refs"] == []
    assert [t["task_id"] for t in config["tasks"]] == ["RSU-001", "RSU-003"]
    result = run(output, config, FakeHost(), TestPointAdapter())
    assert "RSU-003" in result.read_text(encoding="utf-8")
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == original


@pytest.mark.parametrize("file,before,after,error", [
    ("02-sentence-test-point-map.md", "| Q-001 | captured |", "| Q-001 | pending-context |", "not captured"),
    ("02-sentence-test-point-map.md", "| Q-001 | captured |", "| Q-001 | pending |", "not captured"),
    ("02-sentence-test-point-map.md", "| 查询 | 彩票年", "| 其他条件 | 彩票年", "parent wording"),
    ("02-sentence-test-point-map.md", "彩票年只能选择当前年。", "彩票年可以任意选择。", "literal requirement"),
    ("02-sentence-test-point-map.md", "FC-001、DC-001", "FC-999、DC-001", "missing dynamic"),
    ("02-sentence-test-point-map.md", "DC-001、RSU-002", "DC-001、RSU-999", "RSU not found"),
    ("02-sentence-test-point-map.md", "| Q-001 | captured |", "| 待定 | captured |", "unresolvable question"),
    ("03-clarification-questions.md", "| answered |", "| pending |", "unresolved or missing question"),
    ("03-clarification-questions.md", "| answered |", "| deferred |", "unresolved or missing question"),
    ("data-closures/README.md", "| ready |", "| blocked |", "blocked or missing data closure"),
])
def test_dependency_failures_create_no_output(tmp_path: Path, file: str, before: str, after: str, error: str) -> None:
    _, module = fixture(tmp_path)
    replace(module / "preanalysis" / file, before, after)
    output = tmp_path / "bad"
    with pytest.raises(ValueError, match=error):
        setup_test_points(module, output, ["RSU-001"])
    assert not output.exists()


@pytest.mark.parametrize("kind", ["schema", "artifact-escape", "role-path", "output-escape", "duplicate-manifest", "duplicate-rsu", "missing-fixed"])
def test_bad_manifest_and_mapping_fail_closed(tmp_path: Path, kind: str) -> None:
    _, module = fixture(tmp_path)
    pre = module / "preanalysis"
    path = pre / "preanalysis-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if kind == "schema":
        manifest["schema_version"] = "future/v1"
    elif kind == "artifact-escape":
        (module / "outside.md").write_text("external", encoding="utf-8")
        manifest["artifacts"]["readme"] = "../outside.md"
    elif kind == "role-path":
        replace(pre / "02-sentence-test-point-map.md", "[原文](00-module-requirement-pack.md)", "[原文](unused.md)")
    elif kind == "output-escape":
        manifest["output"]["test_points_dir"] = "../../../outside"
    elif kind == "duplicate-manifest":
        (module / "preanalysis-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif kind == "duplicate-rsu":
        replace(pre / "02-sentence-test-point-map.md", "RSU-003 |", "RSU-001 |")
    elif kind == "missing-fixed":
        manifest["resource_roles"]["global_context"] = "SRC-MISSING"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        setup_test_points(module, tmp_path / "bad", ["RSU-001"])
    assert not (tmp_path / "bad").exists()


def test_explicit_index_dependency_and_reference_ranges(tmp_path: Path) -> None:
    project, module = fixture(tmp_path)
    replace(module / "preanalysis" / "02-sentence-test-point-map.md", "DC-001、RSU-002", "DC-001、DC-INDEX、RSU-002")
    inputs = load_preanalysis(module, project)
    assert inputs is not None
    contexts, _ = inputs.task_inputs("RSU-001")
    assert "DC-INDEX" in [item["context_id"] for item in contexts]
    assert set(refs("RSU-001～003；FC-001~FC-002；Q-INDEX")) == {"RSU-001", "RSU-002", "RSU-003", "FC-001", "FC-002", "Q-INDEX"}
    assert split_row(r"| a | `a|b` | c\|d |") == ["a", "`a|b`", r"c\|d"]
    with pytest.raises(ValueError, match="invalid dependency range"):
        refs("RSU-005~003")


def test_pending_unselected_rsu_does_not_block_ready_selected_unit(tmp_path: Path) -> None:
    _, module = fixture(tmp_path)
    replace(module / "preanalysis" / "02-sentence-test-point-map.md", "| 查询 3 | CTX | 无 | captured |", "| 查询 3 | CTX | 无 | pending |")
    setup_test_points(module, tmp_path / "pilot", ["RSU-001"])
    assert (tmp_path / "pilot" / "context-loom.json").is_file()
