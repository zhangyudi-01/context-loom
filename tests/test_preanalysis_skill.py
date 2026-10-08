from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "engineering" / "software-testing" / "requirement-preanalysis"
SCRIPTS = SKILL / "scripts"
REQUIREMENT = "彩票年：下拉选择框，仅当前年和上一年，默认当前年。"


def cli(script: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *(str(a) for a in args)],
                          capture_output=True, text=True, encoding="utf-8", timeout=30)


def fixture(tmp_path: Path, legacy_global: bool = False) -> tuple[Path, Path, Path]:
    project = tmp_path / "source-project"
    module = project / "modules" / "task-list"
    module.mkdir(parents=True)
    global_context = project / ("00-global/00-project-context.md" if legacy_global else "global/project-context.md")
    global_context.parent.mkdir()
    global_context.write_text("# 项目背景\n任务列表查询模块，当前年以浏览器年份为基准。\n", encoding="utf-8")
    source = module / "00-module-requirement-pack.md"
    source.write_text(f"# 彩票年\n\n{REQUIREMENT}\n", encoding="utf-8")
    return module, source, global_context


def scaffold(module: Path, source: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return cli("scaffold_preanalysis.py", module, "--requirement-source", source, *args)


def complete_static_analysis(pre: Path) -> None:
    """A tiny source-faithful analysis fixture, not a fake AI generation claim."""
    values = {
        "CURRENT_GOAL": "建立彩票年字段的完整来源与逻辑基线。",
        "CONTEXT_GOAL": "明确彩票年范围和默认值，不提前生成测试点。",
        "IN_SCOPE": "彩票年下拉选项与默认值。", "OUT_OF_SCOPE": "其他查询字段与查询提交。",
        "MODULE_BACKGROUND": "任务列表中的查询条件。", "MODULE_CAPABILITY": "提供当前年与上一年选项。",
        "MAIN_FLOW": "展示彩票年 -> 默认当前年 -> 用户选择年份",
        "LOGIC_STEP_1": "彩票年只有当前年和上一年，默认当前年。",
        "CONFIRMED_BOUNDARY": "原文无数据库依赖。", "DOMAIN_CONTRACT_BOUNDARY": "保留一个完整字段契约，不逐枚举拆分。",
        "CURRENT_GAP": "无。", "MODULE_SOURCE_LOCATION": "彩票年", "SOURCE_SCOPE": "彩票年",
        "SOURCE_TEXT": REQUIREMENT, "SOURCE_LOCATION": "彩票年", "COVERAGE_NOTE": "字段整体映射，选项和默认值未拆碎。",
        "CONFIRMED_LOGIC_SUMMARY": "彩票年只提供当前年与上一年，默认当前年。", "EXECUTION_PREPARATION": "无。",
    }
    for path in pre.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = "\n".join(line for line in text.splitlines() if not re.match(r"\| Q-\d{3} \|", line)) + "\n"
        for name, value in values.items():
            text = text.replace("{{" + name + "}}", value)
        text = text.replace("待基于真实需求原文完成语义闭合审查；此行仅为结构占位，不代表已确认的 RSU 判定。",
                            "选项与默认值共同约束一个可观察字段，保持完整契约。")
        assert "{{" not in text, (path, re.findall(r"\{\{.*?\}\}", text))
        path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("legacy_global", [False, True])
def test_scaffold_is_self_contained_and_does_not_create_downstream_results(tmp_path: Path, legacy_global: bool) -> None:
    module, source, global_context = fixture(tmp_path, legacy_global)
    source_bytes, global_bytes = source.read_bytes(), global_context.read_bytes()
    result = scaffold(module, source)
    assert result.returncode == 0, result.stderr
    pre = module / "preanalysis"
    manifest = json.loads((pre / "preanalysis-manifest.json").read_text(encoding="utf-8"))
    assert manifest["module_root"] == ".."
    assert manifest["output"]["test_points_dir"] == "../test-points"
    assert (pre / manifest["artifacts"]["module_requirement"]).read_bytes() == source_bytes
    assert global_context.read_bytes() == global_bytes
    assert not (pre / "data-closures").exists()
    assert not (module / "test-points").exists()
    assert not (module / "test-cases").exists()
    assert not list(module.rglob("snapshot-project"))
    skeleton = cli("validate_preanalysis.py", pre, "--require-canonical-layout")
    assert skeleton.returncode != 0
    assert "placeholder" in skeleton.stdout.lower()
    complete_static_analysis(pre)
    validated = cli("validate_preanalysis.py", pre, "--require-canonical-layout")
    assert validated.returncode == 0, validated.stdout + validated.stderr


def test_rerun_and_manifest_refresh_preserve_manual_analysis_and_requirement(tmp_path: Path) -> None:
    module, source, _ = fixture(tmp_path)
    assert scaffold(module, source).returncode == 0
    pre = module / "preanalysis"
    complete_static_analysis(pre)
    original = {p: p.read_bytes() for p in pre.rglob("*") if p.is_file()}
    assert scaffold(module, source).returncode == 0
    assert {p: p.read_bytes() for p in pre.rglob("*") if p.is_file()} == original
    refresh = scaffold(module, source, "--refresh-manifest", "--test-points-dir", module / "new-test-points")
    assert refresh.returncode == 0, refresh.stderr
    assert json.loads((pre / "preanalysis-manifest.json").read_text(encoding="utf-8"))["output"]["test_points_dir"] == "../new-test-points"
    assert {p: p.read_bytes() for p in pre.rglob("*") if p.is_file() and p.name != "preanalysis-manifest.json"} == {
        p: b for p, b in original.items() if p.name != "preanalysis-manifest.json"}
    assert scaffold(module, source, "--force").returncode == 0
    assert (pre / "00-module-requirement-pack.md").read_bytes() == source.read_bytes()


@pytest.mark.parametrize("failure", ["context", "source", "data-source", "output", "legacy-layout"])
def test_invalid_scaffold_inputs_leave_no_partial_directory(tmp_path: Path, failure: str) -> None:
    module, source, _ = fixture(tmp_path)
    args: list[object] = []
    if failure == "context":
        args += ["--global-context", tmp_path / "missing.md"]
    elif failure == "source":
        source = module / "missing.md"
    elif failure == "data-source":
        args += ["--with-data-closures", "--data-source", tmp_path / "missing.md"]
    elif failure == "output":
        args += ["--test-points-dir", tmp_path / "outside"]
    elif failure == "legacy-layout":
        (module / "01-context-pack.md").write_text("旧分析，不可覆盖", encoding="utf-8")
    result = scaffold(module, source, *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert not (module / "preanalysis").exists()


@pytest.mark.parametrize("defect", ["wording", "coverage", "broken-link", "hidden-parent"])
def test_validator_rejects_invalid_completed_analysis(tmp_path: Path, defect: str) -> None:
    module, source, _ = fixture(tmp_path)
    assert scaffold(module, source).returncode == 0
    pre = module / "preanalysis"
    complete_static_analysis(pre)
    map_file = pre / "02-sentence-test-point-map.md"
    text = map_file.read_text(encoding="utf-8")
    if defect == "wording":
        text = text.replace(REQUIREMENT, "彩票年支持任意历史年份。")
    elif defect == "coverage":
        text = text.replace("| mapped | RSU-001 |", "| mapped | RSU-999 |")
    elif defect == "broken-link":
        text = text.replace("./00-module-requirement-pack.md", "./missing.md")
    elif defect == "hidden-parent":
        text = text.replace("| RSU-001 | 无 |", "| RSU-001 | 系统生成任务并进入详情页。 |")
    map_file.write_text(text, encoding="utf-8")
    validated = cli("validate_preanalysis.py", pre, "--require-canonical-layout")
    assert validated.returncode != 0, validated.stdout
    assert "ERROR" in validated.stdout


def test_optional_data_closure_requires_real_source_and_is_initially_blocked(tmp_path: Path) -> None:
    module, source, _ = fixture(tmp_path)
    schema = module.parents[1] / "global" / "schema (current).md"
    schema.write_text("# Schema\ntask(id bigint primary key, status integer)", encoding="utf-8")
    result = scaffold(module, source, "--with-data-closures", "--data-source", schema)
    assert result.returncode == 0, result.stderr
    pre = module / "preanalysis"
    assert (pre / "data-closures" / "DC-001-数据闭包.md").is_file()
    assert "pending-context" in (pre / "02-sentence-test-point-map.md").read_text(encoding="utf-8")
    assert "blocked" in (pre / "data-closures" / "README.md").read_text(encoding="utf-8")
    assert "schema%20%28current%29.md" in (pre / "02-sentence-test-point-map.md").read_text(encoding="utf-8")
    assert cli("validate_preanalysis.py", pre, "--require-canonical-layout").returncode != 0


def test_custom_context_link_with_spaces_and_parentheses_is_clickable(tmp_path: Path) -> None:
    module, source, global_context = fixture(tmp_path)
    custom = global_context.with_name("project context (shared).md")
    global_context.rename(custom)
    result = scaffold(module, source, "--global-context", custom)
    assert result.returncode == 0, result.stderr
    pre = module / "preanalysis"
    assert "project%20context%20%28shared%29.md" in (pre / "02-sentence-test-point-map.md").read_text(encoding="utf-8")
    complete_static_analysis(pre)
    validated = cli("validate_preanalysis.py", pre, "--require-canonical-layout")
    assert validated.returncode == 0, validated.stdout + validated.stderr


def test_installed_skill_runs_without_original_project_or_runtime_paths(tmp_path: Path) -> None:
    module, source, _ = fixture(tmp_path)
    installed = tmp_path / "installed-skills" / "testing-requirement-preanalysis"
    shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    result = subprocess.run([sys.executable, "-X", "utf8", str(installed / "scripts" / "scaffold_preanalysis.py"),
                             str(module), "--requirement-source", str(source)], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    complete_static_analysis(module / "preanalysis")
    validated = subprocess.run([sys.executable, "-X", "utf8", str(installed / "scripts" / "validate_preanalysis.py"),
                                str(module / "preanalysis"), "--require-canonical-layout"], cwd=tmp_path,
                               capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert validated.returncode == 0, validated.stdout + validated.stderr
