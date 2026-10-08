#!/usr/bin/env python3
"""Validate module requirement preanalysis structure, links, IDs, and source fidelity."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


MANIFEST_NAME = "preanalysis-manifest.json"
MANIFEST_SCHEMA = "preanalysis/v1"
CANONICAL_PREANALYSIS_DIR = "preanalysis"
ARTIFACT_KEYS = {
    "readme": "README.md",
    "module_requirement": "00-module-requirement-pack.md",
    "context_pack": "01-context-pack.md",
    "rsu_map": "02-sentence-test-point-map.md",
    "clarifications": "03-clarification-questions.md",
    "context_card_index": "context-cards/README.md",
}
LEGACY_ARTIFACTS = {key: value for key, value in ARTIFACT_KEYS.items()}
RESOURCE_ROLE_KEYS = ("global_context", "module_requirement", "module_context")
LEGACY_RESOURCE_ROLES = {
    "global_context": "SRC-GLOBAL",
    "module_requirement": "SRC-MOD",
    "module_context": "CTX",
}
RESOURCE_ID_PATTERN = re.compile(
    r"(?:SRC-[A-Z0-9-]+|CTX|Q-INDEX|FC-INDEX|RSU-INDEX|DC-INDEX|FC-\d{3}|DC-\d{3})"
)

README_HEADINGS = (
    "当前目标",
    "文件职责",
    "快速索引",
    "分析流程",
    "后续测试点生成输入",
    "后续追溯关系",
    "约束",
)

CONTEXT_HEADINGS = (
    "目标",
    "资源索引",
    "当前阶段边界",
    "资料优先级",
    "模块在需求全文中的背景与定位",
    "模块目标与能力",
    "已确认的详细逻辑",
    "已确认的理解边界",
    "原文、上下文和验证信息的边界",
    "后续测试点生成输入规则",
    "当前缺口",
)

MAP_HEADINGS = (
    "定位",
    "引用入口",
    "当前模块原文单元",
    "原文来源覆盖检查",
    "后续使用规则",
)

QUESTION_HEADINGS = (
    "引用入口",
    "已确认问题与结论",
    "待确认问题",
    "执行准备项",
    "回填规则",
)

TABLE_HEADERS = {
    "readme_files": ("文件", "职责"),
    "context_resources": ("资源 ID", "可点击文件", "用途"),
    "context_boundary": ("信息类型", "保存位置", "示例"),
    "map_resources": ("资源 ID", "可点击文件", "定位用途"),
    "partition": ("来源范围", "语义角色", "拆分处理", "对应 RSU", "判定理由"),
    "rsu": (
        "RSU-ID",
        "父级条件（原文）",
        "原文内容",
        "来源",
        "来源定位",
        "相关上下文",
        "相关问题",
        "状态",
    ),
    "coverage": ("原文来源范围", "处理结果", "对应 RSU/问题", "说明"),
    "answered_q": ("Q-ID", "关联原文/上下文", "状态", "人工确认结论", "回填结果"),
    "pending_q": ("Q-ID", "关联来源", "状态", "问题", "未确认时的处理"),
    "card_index": ("Card ID", "类型", "可点击文件", "职责"),
    "dc_index": ("DC-ID", "业务数据闭包", "可点击文件", "状态", "关联 RSU", "来源资源"),
    "dc_resources": ("资源 ID", "可点击文件", "用途"),
    "dc_io": ("方向", "逻辑对象", "物理载体/字段", "约束", "依据"),
    "dc_tables": ("Table ID", "物理表", "职责", "访问模式", "主键/自然键", "关键字段", "数据所有权"),
    "dc_edges": ("Edge ID", "From", "To", "Join Predicate", "基数", "附加过滤", "依据"),
    "dc_profiles": ("Profile ID", "数据状态目标", "准备策略", "预期推导", "清理策略"),
    "dc_queries": ("用途", "查询入口", "断言口径", "空结果含义", "依据"),
}

RSU_STATUSES = {"captured", "pending-context", "pending"}
SEMANTIC_ROLES = {
    "visual-placeholder",
    "structural-container",
    "field-fragment",
    "independent-contract",
    "composite-contract",
    "unresolved",
}
PARTITION_DECISIONS = {"one-rsu", "not-rsu", "pending"}
COVERAGE_STATUSES = {
    "mapped",
    "indexed-only",
    "scope-excluded",
    "pending-context",
    "pending",
    "not-applicable",
    "not-rsu",
}
Q_STATUSES = {"answered", "pending", "deferred", "out-of-scope"}
DC_STATUSES = {"ready", "test-point-ready", "blocked"}
PARENT_OBSERVABLE_ACTION_RE = re.compile(
    r"(?:生成|创建|新增|删除|作废|更新|修改|保存|提交|写入|发送|推送|上传|下载|导入|导出|"
    r"弹出|打开|关闭|进入|跳转|返回|展示|显示|提示|调用|启动|停止|取消)"
)
PARENT_CONDITION_ONLY_RE = re.compile(
    r"^.{1,120}(?:时|后|前|期间|情况下|条件下)[：，。；]?$"
)
PARENT_STATIC_STATE_ONLY_RE = re.compile(
    r"^(?:当|在)?[^，。；]{0,60}(?:状态|结果)为[^，。；]{1,60}(?:时)?[：，。；]?$"
)
DC_CARD_HEADINGS = (
    "引用入口",
    "定位",
    "关联范围",
    "闭包目标",
    "输入与输出",
    "关系图",
    "表角色",
    "连接与过滤契约",
    "数据状态与准备契约",
    "查询与断言契约",
    "清理与隔离",
    "当前缺口",
)
TEXT_SUFFIXES = {".md", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml", ".xml", ".html"}


@dataclass
class Issue:
    level: str
    message: str
    path: Path | None = None
    line: int | None = None

    def render(self, root: Path) -> str:
        location = ""
        if self.path is not None:
            try:
                display = self.path.relative_to(root)
            except ValueError:
                display = self.path
            location = str(display)
            if self.line is not None:
                location += f":{self.line}"
            location += ": "
        return f"{self.level}: {location}{self.message}"


@dataclass(frozen=True)
class PreanalysisLayout:
    manifest_path: Path | None
    module_root: Path
    paths: dict[str, Path]
    resource_roles: dict[str, str]
    test_points_dir: Path


class ManifestError(RuntimeError):
    pass


def require_exact_keys(value: dict, expected: set[str], label: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise ManifestError(f"{label} keys mismatch; missing={missing}, unknown={unknown}")


def resolve_portable_path(base: Path, raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestError(f"{label} must be a nonempty relative path")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw) or Path(raw).is_absolute():
        raise ManifestError(f"{label} must be relative to the manifest: {raw}")
    return (base / Path(raw)).resolve()


def require_within(path: Path, root: Path, label: str, allow_root: bool = True) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"{label} escapes its allowed root: {path} not under {root}") from exc
    if not allow_root and not relative.parts:
        raise ManifestError(f"{label} cannot be the root itself: {path}")


def load_preanalysis_layout(preanalysis_dir: Path, requested_manifest: Path | None) -> PreanalysisLayout:
    manifest_path = requested_manifest.resolve() if requested_manifest else preanalysis_dir / MANIFEST_NAME
    if requested_manifest is not None and not manifest_path.is_file():
        raise ManifestError(f"manifest does not exist: {manifest_path}")
    if not manifest_path.is_file():
        return PreanalysisLayout(
            None,
            preanalysis_dir,
            {
                internal_name: (preanalysis_dir / configured_path).resolve()
                for configured_path, internal_name in (
                    (LEGACY_ARTIFACTS[key], ARTIFACT_KEYS[key]) for key in ARTIFACT_KEYS
                )
            },
            dict(LEGACY_RESOURCE_ROLES),
            preanalysis_dir / "test-points",
        )

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {manifest_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be a JSON object")
    require_exact_keys(
        data,
        {"schema_version", "module_root", "artifacts", "resource_roles", "output"},
        "manifest",
    )
    if data["schema_version"] != MANIFEST_SCHEMA:
        raise ManifestError(
            f"unsupported manifest schema: {data['schema_version']}; expected {MANIFEST_SCHEMA}"
        )

    manifest_dir = manifest_path.parent.resolve()
    if manifest_dir != preanalysis_dir:
        raise ManifestError(
            f"manifest must be stored in the preanalysis directory: {manifest_path}"
        )
    module_root = resolve_portable_path(manifest_dir, data["module_root"], "module_root")
    if not module_root.is_dir():
        raise ManifestError(f"module_root does not exist: {module_root}")
    require_within(preanalysis_dir, module_root, "preanalysis directory")

    artifacts = data["artifacts"]
    if not isinstance(artifacts, dict):
        raise ManifestError("artifacts must be a JSON object")
    require_exact_keys(artifacts, set(ARTIFACT_KEYS), "artifacts")
    paths: dict[str, Path] = {}
    seen_paths: set[Path] = set()
    for logical_key, internal_name in ARTIFACT_KEYS.items():
        resolved = resolve_portable_path(manifest_dir, artifacts[logical_key], f"artifacts.{logical_key}")
        require_within(resolved, preanalysis_dir, f"artifacts.{logical_key}")
        if resolved in seen_paths:
            raise ManifestError(f"multiple artifact roles point to the same file: {resolved}")
        seen_paths.add(resolved)
        paths[internal_name] = resolved

    roles = data["resource_roles"]
    if not isinstance(roles, dict):
        raise ManifestError("resource_roles must be a JSON object")
    require_exact_keys(roles, set(RESOURCE_ROLE_KEYS), "resource_roles")
    if len(set(roles.values())) != len(RESOURCE_ROLE_KEYS):
        raise ManifestError("resource_roles values must be unique")
    for role, resource_id in roles.items():
        if not isinstance(resource_id, str) or not re.fullmatch(r"(?:SRC-[A-Z0-9-]+|CTX)", resource_id):
            raise ManifestError(f"resource_roles.{role} has invalid resource ID: {resource_id}")
    for role in ("global_context", "module_requirement"):
        if not roles[role].startswith("SRC-"):
            raise ManifestError(f"resource_roles.{role} must use a SRC-* resource ID")

    output = data["output"]
    if not isinstance(output, dict):
        raise ManifestError("output must be a JSON object")
    require_exact_keys(output, {"test_points_dir"}, "output")
    test_points_dir = resolve_portable_path(
        manifest_dir, output["test_points_dir"], "output.test_points_dir"
    )
    require_within(test_points_dir, module_root, "output.test_points_dir", allow_root=False)
    return PreanalysisLayout(manifest_path, module_root, paths, dict(roles), test_points_dir)


@dataclass
class Table:
    headers: tuple[str, ...]
    rows: list[tuple[int, list[str]]]
    line: int


def split_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]

    cells: list[str] = []
    buffer: list[str] = []
    escaped = False
    in_code = False
    for char in text:
        if escaped:
            buffer.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            buffer.append(char)
            continue
        if char == "`":
            in_code = not in_code
            buffer.append(char)
            continue
        if char == "|" and not in_code:
            cells.append("".join(buffer).strip())
            buffer = []
            continue
        buffer.append(char)
    cells.append("".join(buffer).strip())
    return cells


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def extract_tables(text: str) -> list[Table]:
    lines = text.splitlines()
    tables: list[Table] = []
    index = 0
    while index + 1 < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        headers = split_table_row(lines[index])
        separator = split_table_row(lines[index + 1])
        if len(headers) != len(separator) or not is_separator_row(separator):
            index += 1
            continue
        rows: list[tuple[int, list[str]]] = []
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
            cells = split_table_row(lines[cursor])
            if len(cells) == len(headers):
                rows.append((cursor + 1, cells))
            cursor += 1
        tables.append(Table(tuple(headers), rows, index + 1))
        index = cursor
    return tables


def headings(text: str, level: int = 2) -> list[tuple[int, str]]:
    marker = "#" * level
    result: list[tuple[int, str]] = []
    fence_char: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        fence = re.match(r"^\s*([\x60~]{3,})", line)
        if fence:
            current_char = fence.group(1)[0]
            if fence_char is None:
                fence_char = current_char
            elif current_char == fence_char:
                fence_char = None
            continue
        if fence_char is not None:
            continue
        match = re.match(rf"^{re.escape(marker)}\s+(.+?)\s*$", line)
        if match:
            result.append((number, match.group(1)))
    return result


def require_single_h1(issues: list[Issue], path: Path, text: str) -> None:
    h1 = headings(text, level=1)
    if len(h1) != 1:
        issues.append(Issue("ERROR", f"expected exactly one H1, found {len(h1)}", path))
        return
    if h1[0][0] != 1:
        issues.append(Issue("ERROR", "H1 must be the first line", path, h1[0][0]))


def require_heading_order(
    issues: list[Issue], path: Path, text: str, required: tuple[str, ...]
) -> None:
    actual = headings(text)
    previous = 0
    for name in required:
        occurrences = [line for line, actual_name in actual if actual_name == name]
        if not occurrences:
            issues.append(Issue("ERROR", f"missing required heading: ## {name}", path))
            continue
        if len(occurrences) > 1:
            issues.append(Issue("ERROR", f"duplicate required heading: ## {name}", path, occurrences[1]))
        line = occurrences[0]
        if line <= previous:
            issues.append(Issue("ERROR", f"heading is out of order: ## {name}", path, line))
        previous = line


def find_table(tables: list[Table], header: tuple[str, ...]) -> list[Table]:
    return [table for table in tables if table.headers == header]


def require_table(
    issues: list[Issue],
    path: Path,
    tables: list[Table],
    header: tuple[str, ...],
    *,
    allow_multiple: bool = False,
) -> list[Table]:
    matches = find_table(tables, header)
    if not matches:
        issues.append(Issue("ERROR", f"missing fixed table header: {' | '.join(header)}", path))
    elif not allow_multiple and len(matches) > 1:
        issues.append(Issue("ERROR", f"duplicate fixed table: {' | '.join(header)}", path, matches[1].line))
    return matches


def validate_nonempty_table_cells(issues: list[Issue], path: Path, tables: list[Table]) -> None:
    for table in tables:
        for line, cells in table.rows:
            for header, cell in zip(table.headers, cells):
                if not cell.strip():
                    issues.append(Issue("ERROR", f"empty table cell; write '无' in column {header}", path, line))


def normalize_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    return target


def is_external_link(target: str) -> bool:
    return re.match(r"^(?:https?://|mailto:|data:)", target, re.IGNORECASE) is not None


def extract_link_target(cell: str) -> str | None:
    match = re.search(r"!?\[[^\]]*\]\(([^)]+)\)", cell)
    if not match:
        return None
    return normalize_link_target(match.group(1))


def resolve_local_link(source_file: Path, raw_target: str) -> Path | None:
    target = normalize_link_target(raw_target)
    if is_external_link(target) or target.startswith("#"):
        return None
    target = target.split("#", 1)[0]
    if not target:
        return None
    target = unquote(target)
    return (source_file.parent / Path(target)).resolve()


def validate_links(
    issues: list[Issue],
    module_dir: Path,
    excluded_names: set[str],
    excluded_roots: set[Path] | None = None,
) -> tuple[int, int]:
    checked = 0
    broken = 0
    resolved_excluded_roots = {
        root.resolve() for root in (excluded_roots or set())
    }
    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    for path in module_dir.rglob("*.md"):
        resolved_path = path.resolve()
        if any(
            resolved_path == root or root in resolved_path.parents
            for root in resolved_excluded_roots
        ):
            continue
        if path.name in excluded_names:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in pattern.finditer(line):
                raw_target = match.group(1).strip()
                normalized_target = normalize_link_target(raw_target)
                if not is_external_link(normalized_target) and "#" in normalized_target:
                    issues.append(
                        Issue(
                            "ERROR",
                            f"local Markdown fragment links are forbidden; use a file link plus semantic location: {raw_target}",
                            path,
                            line_number,
                        )
                    )
                resolved = resolve_local_link(path, raw_target)
                if resolved is None:
                    continue
                checked += 1
                if not resolved.exists():
                    broken += 1
                    issues.append(
                        Issue("ERROR", f"broken local Markdown link: {raw_target}", path, line_number)
                    )
    return checked, broken


def expand_ids(text: str, prefix: str) -> set[str]:
    pattern = re.compile(
        rf"{re.escape(prefix)}-(\d{{3}})(?:\s*[～~]\s*(?:{re.escape(prefix)}-)?(\d{{3}}))?"
    )
    result: set[str] = set()
    for start_text, end_text in pattern.findall(text):
        start = int(start_text)
        end = int(end_text) if end_text else start
        if end < start or end - start > 500:
            result.add(f"{prefix}-{start:03d}")
            if end_text:
                result.add(f"{prefix}-{end:03d}")
            continue
        result.update(f"{prefix}-{value:03d}" for value in range(start, end + 1))
    return result


def normalize_source_text(text: str) -> str:
    value = html.unescape(text).replace("\u00a0", " ")
    # Images are visual placeholders rather than requirement wording. Drop them
    # before normalizing ordinary links so a composite contract may span an
    # inline prototype image without inheriting its alt text (for example,
    # ``image.png``) as fake source content.
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"</?[A-Za-z][^>]*>", "", value)
    value = re.sub(r"\\([\\`*_{}\[\]()#+.!|>-])", r"\1", value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s{0,3}>+\s?", "", value)
    value = re.sub(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+", "", value)
    value = re.sub(r"(^|[：；。])\s*\d+[.)]\s+", r"\1", value, flags=re.MULTILINE)
    value = value.replace("~~", "").replace("**", "").replace("*", "").replace("`", "")
    value = re.sub(r"(?<!\w)_{1,2}(?=\S)", "", value)
    value = re.sub(r"(?<=\S)_{1,2}(?!\w)", "", value)
    value = re.sub(r"\s+", "", value)
    return value.strip()


def parent_has_observable_behavior(text: str) -> bool:
    """Return true for high-confidence actions/results that must not live only in a parent cell."""

    normalized = normalize_source_text(text)
    if not normalized or normalized == "无":
        return False
    probe = re.sub(r"【[^】]*】|“[^”]*”|\"[^\"]*\"|'[^']*'", "", normalized)
    if PARENT_CONDITION_ONLY_RE.fullmatch(probe) or PARENT_STATIC_STATE_ONLY_RE.fullmatch(probe):
        return False
    return PARENT_OBSERVABLE_ACTION_RE.search(probe) is not None


def parse_resource_table(
    issues: list[Issue], map_path: Path, tables: list[Table]
) -> tuple[dict[str, Path], set[str]]:
    matches = require_table(issues, map_path, tables, TABLE_HEADERS["map_resources"])
    resources: dict[str, Path] = {}
    all_ids: set[str] = set()
    if not matches:
        return resources, all_ids

    for line, cells in matches[0].rows:
        resource_id = cells[0].strip("`")
        if RESOURCE_ID_PATTERN.fullmatch(resource_id) is None:
            issues.append(Issue("ERROR", f"invalid resource ID: {resource_id}", map_path, line))
            continue
        if resource_id in all_ids:
            issues.append(Issue("ERROR", f"duplicate resource ID: {resource_id}", map_path, line))
            continue
        all_ids.add(resource_id)
        target = extract_link_target(cells[1])
        if target is None:
            issues.append(Issue("ERROR", f"resource {resource_id} has no clickable file", map_path, line))
            continue
        resolved = resolve_local_link(map_path, target)
        if resolved is not None:
            resources[resource_id] = resolved
    return resources, all_ids


def parse_context_resource_table(
    issues: list[Issue], context_path: Path, tables: list[Table]
) -> tuple[dict[str, Path], set[str]]:
    matches = find_table(tables, TABLE_HEADERS["context_resources"])
    resources: dict[str, Path] = {}
    all_ids: set[str] = set()
    if not matches:
        return resources, all_ids

    for line, cells in matches[0].rows:
        resource_id = cells[0].strip("`")
        if RESOURCE_ID_PATTERN.fullmatch(resource_id) is None:
            issues.append(Issue("ERROR", f"invalid Context Pack resource ID: {resource_id}", context_path, line))
            continue
        if resource_id in all_ids:
            issues.append(Issue("ERROR", f"duplicate Context Pack resource ID: {resource_id}", context_path, line))
            continue
        all_ids.add(resource_id)
        target = extract_link_target(cells[1])
        if target is None:
            issues.append(Issue("ERROR", f"Context Pack resource {resource_id} has no clickable file", context_path, line))
            continue
        resolved = resolve_local_link(context_path, target)
        if resolved is not None:
            resources[resource_id] = resolved
    return resources, all_ids


def validate_fixed_inputs(
    issues: list[Issue], path: Path, text: str, resource_roles: dict[str, str]
) -> None:
    checks = {
        "global context full input": resource_roles["global_context"] in text,
        "module requirement full input": resource_roles["module_requirement"] in text,
        "module logic baseline": "模块背景" in text and "详细逻辑" in text,
        "current RSU mapping row": "RSU-ID" in text and re.search(r"当前.*RSU-ID", text) is not None,
    }
    for label, present in checks.items():
        if not present:
            issues.append(Issue("ERROR", f"missing fixed-input contract: {label}", path))


def validate_source_match(
    issues: list[Issue], map_path: Path, rsu_rows: list[tuple[int, list[str]]], resources: dict[str, Path]
) -> tuple[int, int]:
    checked = 0
    skipped = 0
    source_cache: dict[Path, str] = {}

    for line, cells in rsu_rows:
        rsu_id, parent_text, source_text, source_id, _, _, _, status = cells
        source_id = source_id.strip("`")
        status = status.strip("`")
        source_path = resources.get(source_id)
        if source_path is None:
            issues.append(Issue("ERROR", f"{rsu_id} source is not resolvable: {source_id}", map_path, line))
            continue
        if not source_path.is_file():
            issues.append(Issue("ERROR", f"{rsu_id} source file does not exist: {source_path}", map_path, line))
            continue
        if source_path.suffix.lower() not in TEXT_SUFFIXES:
            skipped += 1
            if status == "captured":
                issues.append(
                    Issue(
                        "ERROR",
                        f"{rsu_id} uses non-text source {source_path.name}; provide a text mirror or mark it pending",
                        map_path,
                        line,
                    )
                )
            continue
        try:
            source_normalized = source_cache.setdefault(
                source_path,
                normalize_source_text(source_path.read_text(encoding="utf-8")),
            )
        except UnicodeDecodeError:
            skipped += 1
            issues.append(
                Issue("ERROR", f"{rsu_id} source is not UTF-8 readable: {source_path}", map_path, line)
            )
            continue
        row_normalized = normalize_source_text(source_text)
        if not row_normalized:
            issues.append(Issue("ERROR", f"{rsu_id} has empty source text", map_path, line))
            continue
        checked += 1
        if row_normalized not in source_normalized:
            issues.append(
                Issue(
                    "ERROR",
                    f"{rsu_id} source text does not match normalized content in {source_path.name}",
                    map_path,
                    line,
                )
            )
        parent_normalized = normalize_source_text(parent_text)
        if parent_normalized and parent_normalized != "无" and parent_normalized not in source_normalized:
            issues.append(
                Issue(
                    "ERROR",
                    f"{rsu_id} parent source text does not match normalized content in {source_path.name}",
                    map_path,
                    line,
                )
            )
    return checked, skipped


def parse_source_scope(value: str) -> tuple[str, str] | None:
    """Return a stable key for a `SRC-ID > semantic location` table cell."""

    source_scope = value.strip("`").strip()
    match = re.fullmatch(r"(SRC-[A-Z0-9-]+)\s*>\s*(\S(?:.*\S)?)", source_scope)
    if match is None:
        return None
    semantic_location = re.sub(r"\s+", " ", match.group(2)).strip()
    return match.group(1), semantic_location


def validate_partition_decisions(
    issues: list[Issue],
    map_path: Path,
    partition_tables: list[Table],
    rsu_ids: set[str],
    resource_ids: set[str],
) -> list[tuple[int, list[str]]]:
    """Validate the semantic pass that must precede RSU row creation."""

    if not partition_tables:
        return []
    if len(partition_tables) > 1:
        issues.append(
            Issue(
                "ERROR",
                "duplicate fixed table: " + " | ".join(TABLE_HEADERS["partition"]),
                map_path,
                partition_tables[1].line,
            )
        )

    rows = partition_tables[0].rows
    if not rows:
        issues.append(Issue("ERROR", "partition decision table has no rows", map_path, partition_tables[0].line))
        return rows

    decision_rsus: set[str] = set()
    seen_scopes: set[tuple[str, str]] = set()
    expected_decisions = {
        "visual-placeholder": "not-rsu",
        "structural-container": "not-rsu",
        "field-fragment": "not-rsu",
        "independent-contract": "one-rsu",
        "composite-contract": "one-rsu",
        "unresolved": "pending",
    }

    for line, cells in rows:
        source_scope = cells[0].strip("`").strip()
        scope_key = parse_source_scope(cells[0])
        if scope_key is None:
            issues.append(
                Issue(
                    "ERROR",
                    "partition source scope must use 'SRC-ID > semantic location'",
                    map_path,
                    line,
                )
            )
        elif scope_key[0] not in resource_ids:
            issues.append(
                Issue(
                    "ERROR",
                    f"partition decision references undefined resource: {scope_key[0]}",
                    map_path,
                    line,
                )
            )
        comparable_scope = scope_key or ("INVALID", source_scope)
        if comparable_scope in seen_scopes:
            issues.append(Issue("ERROR", f"duplicate partition source scope: {source_scope}", map_path, line))
        seen_scopes.add(comparable_scope)

        role = cells[1].strip("`")
        decision = cells[2].strip("`")
        if role not in SEMANTIC_ROLES:
            issues.append(Issue("ERROR", f"invalid semantic role: {role}", map_path, line))
        if decision not in PARTITION_DECISIONS:
            issues.append(Issue("ERROR", f"invalid partition decision: {decision}", map_path, line))
        if role in expected_decisions and decision != expected_decisions[role]:
            issues.append(
                Issue(
                    "ERROR",
                    f"semantic role {role} requires partition decision {expected_decisions[role]}, got {decision}",
                    map_path,
                    line,
                )
            )

        corresponding = cells[3].strip("`").strip()
        referenced_rsus = expand_ids(corresponding, "RSU")
        if decision == "one-rsu":
            decision_rsus.update(referenced_rsus)
        for rsu_id in referenced_rsus:
            if rsu_id not in rsu_ids:
                issues.append(Issue("ERROR", f"partition decision references undefined {rsu_id}", map_path, line))
        if not corresponding:
            issues.append(Issue("ERROR", "partition decision has empty corresponding RSU cell", map_path, line))
        if decision == "one-rsu" and len(referenced_rsus) != 1:
            issues.append(
                Issue(
                    "ERROR",
                    f"one-rsu decision must reference exactly one RSU, found {sorted(referenced_rsus)}",
                    map_path,
                    line,
                )
            )
        absorbing_field_fragment = role == "field-fragment" and decision == "not-rsu"
        if decision in {"not-rsu", "pending"} and referenced_rsus and not absorbing_field_fragment:
            issues.append(
                Issue(
                    "ERROR",
                    f"{decision} decision must not create a standalone RSU; remove references {sorted(referenced_rsus)}",
                    map_path,
                    line,
                )
            )
        if role == "field-fragment" and decision == "not-rsu" and not referenced_rsus:
            issues.append(
                Issue(
                    "ERROR",
                    "field-fragment must reference the composite RSU that absorbs it",
                    map_path,
                    line,
                )
            )
        if role in {"visual-placeholder", "structural-container", "unresolved"} and corresponding != "无":
            issues.append(
                Issue(
                    "ERROR",
                    f"{role} must use '无' in 对应 RSU unless it is represented by a complete one-rsu range",
                    map_path,
                    line,
                )
            )
        if role == "field-fragment" and corresponding == "无":
            issues.append(Issue("ERROR", "field-fragment cannot use '无' in 对应 RSU", map_path, line))

        if not cells[4].strip() or cells[4].strip() == "无":
            issues.append(Issue("ERROR", "partition decision must include a semantic reason", map_path, line))

    for rsu_id in sorted(rsu_ids - decision_rsus):
        issues.append(Issue("ERROR", f"{rsu_id} is missing from one-rsu partition decisions", map_path))
    return rows


def validate_partition_coverage_consistency(
    issues: list[Issue],
    map_path: Path,
    partition_rows: list[tuple[int, list[str]]],
    coverage_rows: list[tuple[int, list[str]]],
    q_statuses: dict[str, str],
) -> None:
    """Require the semantic partition pass and source coverage ledger to agree."""

    if not partition_rows:
        return

    partition_by_scope: dict[tuple[str, str], tuple[int, list[str]]] = {}
    for line, cells in partition_rows:
        scope_key = parse_source_scope(cells[0])
        if scope_key is not None:
            partition_by_scope.setdefault(scope_key, (line, cells))

    coverage_by_scope: dict[tuple[str, str], tuple[int, list[str]]] = {}
    for line, cells in coverage_rows:
        scope_key = parse_source_scope(cells[0])
        if scope_key is not None:
            coverage_by_scope.setdefault(scope_key, (line, cells))

    expected_statuses = {
        "one-rsu": {"mapped"},
        "not-rsu": {"not-rsu"},
        "pending": {"pending", "pending-context"},
    }
    semantic_coverage_statuses = {status for values in expected_statuses.values() for status in values}

    for scope_key, (partition_line, partition_cells) in partition_by_scope.items():
        display_scope = f"{scope_key[0]} > {scope_key[1]}"
        coverage_entry = coverage_by_scope.get(scope_key)
        if coverage_entry is None:
            issues.append(
                Issue(
                    "ERROR",
                    f"partition source scope is missing from source coverage: {display_scope}",
                    map_path,
                    partition_line,
                )
            )
            continue

        coverage_line, coverage_cells = coverage_entry
        role = partition_cells[1].strip("`")
        decision = partition_cells[2].strip("`")
        coverage_status = coverage_cells[1].strip("`")
        allowed_statuses = expected_statuses.get(decision)
        if allowed_statuses is not None and coverage_status not in allowed_statuses:
            issues.append(
                Issue(
                    "ERROR",
                    f"partition decision {decision} for {display_scope} requires coverage status "
                    f"{sorted(allowed_statuses)}, got {coverage_status}",
                    map_path,
                    coverage_line,
                )
            )

        partition_rsus = expand_ids(partition_cells[3], "RSU")
        coverage_rsus = expand_ids(coverage_cells[2], "RSU")
        if partition_rsus != coverage_rsus:
            issues.append(
                Issue(
                    "ERROR",
                    f"partition and coverage RSU references differ for {display_scope}: "
                    f"partition={sorted(partition_rsus)}, coverage={sorted(coverage_rsus)}",
                    map_path,
                    coverage_line,
                )
            )

        if decision == "pending":
            referenced_qs = expand_ids(coverage_cells[2], "Q")
            if not referenced_qs:
                issues.append(
                    Issue(
                        "ERROR",
                        f"pending partition scope must reference at least one Q-ID in source coverage: {display_scope}",
                        map_path,
                        coverage_line,
                    )
                )
            for q_id in referenced_qs:
                if q_statuses.get(q_id) not in {"pending", "deferred"}:
                    issues.append(
                        Issue(
                            "ERROR",
                            f"pending partition scope must reference a pending/deferred Q-ID, got {q_id}: "
                            f"{q_statuses.get(q_id, 'undefined')}",
                            map_path,
                            coverage_line,
                        )
                    )
            if coverage_rsus:
                issues.append(
                    Issue(
                        "ERROR",
                        f"pending partition scope must not reference an RSU in source coverage: {display_scope}",
                        map_path,
                        coverage_line,
                    )
                )
        if role == "field-fragment" and decision == "not-rsu" and not coverage_rsus:
            issues.append(
                Issue(
                    "ERROR",
                    f"field-fragment coverage must reference the composite RSU that absorbs it: {display_scope}",
                    map_path,
                    coverage_line,
                )
            )

    for scope_key, (coverage_line, coverage_cells) in coverage_by_scope.items():
        coverage_status = coverage_cells[1].strip("`")
        if coverage_status not in semantic_coverage_statuses or scope_key in partition_by_scope:
            continue
        display_scope = f"{scope_key[0]} > {scope_key[1]}"
        issues.append(
            Issue(
                "ERROR",
                f"source coverage status {coverage_status} requires a matching partition decision: {display_scope}",
                map_path,
                coverage_line,
            )
        )


def validate_rsu_source_shape(
    issues: list[Issue],
    map_path: Path,
    rsu_rows: list[tuple[int, list[str]]],
) -> None:
    """Catch source ranges that are visibly not independently consumable RSUs."""

    obvious_non_rsu = {
        "原型",
        "查询条件包括：",
        "包含以下信息：",
        "任务列表的行内操作：",
    }
    dangling_child_leadin = re.compile(r"(?:包括|包含以下(?:信息|内容)|行内操作)：$")
    location_label = re.compile(r"^(?:(?:业务\s*)?规则\s*)?\d+(?:\.\d+)?$|^(?:业务\s*)?规则$")
    plain_field_fragment = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9_()（）、-]+[；。]$")
    enum_field_fragment = re.compile(
        r"^[\u4e00-\u9fffA-Za-z0-9_()（）、-]+，包括[\u4e00-\u9fffA-Za-z0-9_()（）、-]+[；。]$"
    )
    contract_signals = (
        "点击",
        "提供",
        "显示",
        "跳转",
        "执行",
        "支持",
        "仅",
        "默认为",
        "下拉",
        "输入框",
        "按钮",
        "弹窗",
        "按照",
        "按",
        "可",
        "需",
        "应",
    )
    normalized_sources = [
        (cells[0].strip("`"), normalize_source_text(cells[2]))
        for _, cells in rsu_rows
    ]
    hidden_parent_groups: dict[str, list[tuple[int, str, str]]] = {}

    for line, cells in rsu_rows:
        rsu_id = cells[0].strip("`")
        source_text = normalize_source_text(cells[2])
        if source_text in obvious_non_rsu:
            issues.append(
                Issue(
                    "ERROR",
                    f"{rsu_id} source content is only a visual placeholder or structural container; it cannot be a standalone RSU",
                    map_path,
                    line,
                )
            )
        elif dangling_child_leadin.search(source_text):
            issues.append(
                Issue(
                    "ERROR",
                    f"{rsu_id} source content ends with a child-list lead-in but omits the required child items; "
                    "merge the complete parent/child contract",
                    map_path,
                    line,
                )
            )
        if (
            (plain_field_fragment.fullmatch(source_text) or enum_field_fragment.fullmatch(source_text))
            and not any(signal in source_text for signal in contract_signals)
        ):
            issues.append(
                Issue(
                    "ERROR",
                    f"{rsu_id} source content is only a field or enum fragment; merge it into the complete parent/result contract",
                    map_path,
                    line,
                )
            )
        parent_text = normalize_source_text(cells[1])
        if parent_text != "无" and location_label.fullmatch(parent_text):
            issues.append(
                Issue(
                    "ERROR",
                    f"{rsu_id} 父级条件（原文） uses a location label instead of source wording; put the label in 来源定位",
                    map_path,
                    line,
                )
            )
        if parent_has_observable_behavior(parent_text):
            represented = any(
                parent_text in source_text
                for _, source_text in normalized_sources
                if source_text
            )
            if not represented:
                hidden_parent_groups.setdefault(parent_text, []).append((line, rsu_id, cells[1]))

    for affected in hidden_parent_groups.values():
        line, _, original_parent = affected[0]
        rsu_list = ", ".join(item[1] for item in affected)
        issues.append(
            Issue(
                "ERROR",
                f"observable parent behavior is hidden from every 原文内容 cell for {rsu_list}: "
                f"{original_parent}. Create a standalone RSU for the complete parent wording, or merge it "
                "into a composite RSU's 原文内容; child rows may retain only the minimal condition clause",
                map_path,
                line,
            )
        )


def extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def validate_data_closures(
    issues: list[Issue],
    preanalysis_dir: Path,
    map_path: Path,
    context_path: Path,
    resources: dict[str, Path],
    resource_ids: set[str],
    context_resources: dict[str, Path],
    context_resource_ids: set[str],
    rsu_rows: list[tuple[int, list[str]]],
    rsu_ids: set[str],
    q_rows: list[tuple[int, list[str]]],
    q_ids: set[str],
    fc_ids: set[str],
) -> int:
    map_dc_ids = {item for item in resource_ids if re.fullmatch(r"DC-\d{3}", item)}
    context_dc_ids = {
        item for item in context_resource_ids if re.fullmatch(r"DC-\d{3}", item)
    }
    enabled = bool(
        map_dc_ids
        or context_dc_ids
        or "DC-INDEX" in resource_ids
        or "DC-INDEX" in context_resource_ids
    )
    if not enabled:
        return 0

    if "DC-INDEX" not in resource_ids:
        issues.append(Issue("ERROR", "data closures are enabled but map is missing DC-INDEX", map_path))
    if "DC-INDEX" not in context_resource_ids:
        issues.append(
            Issue("ERROR", "data closures are enabled but Context Pack is missing DC-INDEX", context_path)
        )
    index_path = resources.get("DC-INDEX")
    context_index_path = context_resources.get("DC-INDEX")
    if index_path is not None and context_index_path is not None and index_path != context_index_path:
        issues.append(
            Issue(
                "ERROR",
                f"DC-INDEX targets differ between map and Context Pack: {index_path} != {context_index_path}",
                context_path,
            )
        )
    if index_path is None or not index_path.is_file():
        issues.append(Issue("ERROR", f"DC-INDEX file is missing or unresolved: {index_path}", map_path))
        return 0
    try:
        index_path.relative_to(preanalysis_dir)
    except ValueError:
        issues.append(Issue("ERROR", "DC-INDEX must stay inside the preanalysis directory", index_path))

    index_text = index_path.read_text(encoding="utf-8")
    require_single_h1(issues, index_path, index_text)
    require_heading_order(
        issues,
        index_path,
        index_text,
        ("闭包索引", "状态定义", "使用规则"),
    )
    if re.search(r"\{\{[A-Z0-9_]+\}\}", index_text):
        issues.append(Issue("ERROR", "unresolved template placeholder", index_path))
    index_tables = extract_tables(index_text)
    index_matches = require_table(
        issues, index_path, index_tables, TABLE_HEADERS["dc_index"]
    )
    validate_nonempty_table_cells(issues, index_path, index_tables)
    if not index_matches:
        return 0

    indexed_cards: dict[str, tuple[Path, str, set[str], set[str], int]] = {}
    for line, cells in index_matches[0].rows:
        dc_id = cells[0].strip("`")
        if not re.fullmatch(r"DC-\d{3}", dc_id):
            issues.append(Issue("ERROR", f"invalid data closure ID: {dc_id}", index_path, line))
            continue
        if dc_id in indexed_cards:
            issues.append(Issue("ERROR", f"duplicate data closure ID: {dc_id}", index_path, line))
            continue
        status = cells[3].strip("`")
        if status not in DC_STATUSES:
            issues.append(Issue("ERROR", f"invalid {dc_id} status: {status}", index_path, line))
        related_rsus = expand_ids(cells[4], "RSU")
        if not related_rsus:
            issues.append(Issue("ERROR", f"{dc_id} index row must reference at least one RSU", index_path, line))
        for rsu_id in related_rsus:
            if rsu_id not in rsu_ids:
                issues.append(Issue("ERROR", f"{dc_id} references undefined {rsu_id}", index_path, line))
        source_resources = set(RESOURCE_ID_PATTERN.findall(cells[5]))
        if not source_resources:
            issues.append(Issue("ERROR", f"{dc_id} index row has no source resource", index_path, line))
        for resource_id in source_resources:
            if resource_id not in resource_ids and resource_id not in context_resource_ids:
                issues.append(
                    Issue("ERROR", f"{dc_id} references undefined source resource {resource_id}", index_path, line)
                )
        target = extract_link_target(cells[2])
        if target is None:
            issues.append(Issue("ERROR", f"{dc_id} has no clickable card", index_path, line))
            continue
        card_path = resolve_local_link(index_path, target)
        if card_path is None:
            issues.append(Issue("ERROR", f"{dc_id} card must be a local file", index_path, line))
            continue
        indexed_cards[dc_id] = (card_path, status, related_rsus, source_resources, line)

    indexed_ids = set(indexed_cards)
    validate_sequence(issues, index_path, indexed_ids, "DC")
    if not indexed_ids:
        issues.append(Issue("ERROR", "enabled data closure index has no cards", index_path))
    if missing := indexed_ids - map_dc_ids:
        issues.append(Issue("ERROR", f"data closure cards missing from map resource index: {sorted(missing)}", map_path))
    if extra := map_dc_ids - indexed_ids:
        issues.append(Issue("ERROR", f"map references data closure cards absent from DC-INDEX: {sorted(extra)}", map_path))
    if extra := context_dc_ids - indexed_ids:
        issues.append(
            Issue("ERROR", f"Context Pack references data closure cards absent from DC-INDEX: {sorted(extra)}", context_path)
        )

    rsu_status = {cells[0].strip("`"): cells[7].strip("`") for _, cells in rsu_rows}
    q_status = {cells[0].strip("`"): cells[2].strip("`") for _, cells in q_rows}
    for dc_id, (card_path, status, related_rsus, source_resources, _) in indexed_cards.items():
        map_target = resources.get(dc_id)
        if map_target is not None and map_target != card_path:
            issues.append(Issue("ERROR", f"map resource {dc_id} points to the wrong file: {map_target}", map_path))
        context_target = context_resources.get(dc_id)
        if context_target is not None and context_target != card_path:
            issues.append(
                Issue("ERROR", f"Context Pack resource {dc_id} points to the wrong file: {context_target}", context_path)
            )
        if not card_path.is_file():
            issues.append(Issue("ERROR", f"data closure card does not exist: {card_path}", index_path))
            continue
        try:
            card_path.relative_to(preanalysis_dir)
        except ValueError:
            issues.append(Issue("ERROR", f"{dc_id} card must stay inside the preanalysis directory", card_path))
        if not card_path.name.startswith(f"{dc_id}-"):
            issues.append(Issue("ERROR", f"data closure filename must start with {dc_id}-", card_path))

        card_text = card_path.read_text(encoding="utf-8")
        require_single_h1(issues, card_path, card_text)
        first_heading = next((name for _, name in headings(card_text, level=1)), "")
        if not first_heading.startswith(dc_id):
            issues.append(Issue("ERROR", f"H1 must start with {dc_id}", card_path, 1))
        require_heading_order(issues, card_path, card_text, DC_CARD_HEADINGS)
        if re.search(r"\{\{[A-Z0-9_]+\}\}", card_text):
            issues.append(Issue("ERROR", "unresolved template placeholder", card_path))
        if re.search(r"(?ms)^```mermaid\s*$.*?\bflowchart\b.*?^```\s*$", card_text) is None:
            issues.append(Issue("ERROR", "data closure relationship graph must contain a Mermaid flowchart", card_path))

        status_match = re.search(
            r"(?m)^-\s*状态：\s*`?(ready|test-point-ready|blocked)`?\s*$",
            extract_section(card_text, "定位"),
        )
        if status_match is None:
            issues.append(Issue("ERROR", f"{dc_id} 定位 section must declare its fixed status", card_path))
        elif status_match.group(1) != status:
            issues.append(
                Issue("ERROR", f"{dc_id} card status {status_match.group(1)} does not match index status {status}", card_path)
            )

        card_tables = extract_tables(card_text)
        resource_matches = require_table(
            issues, card_path, card_tables, TABLE_HEADERS["dc_resources"]
        )
        required_tables: dict[str, list[Table]] = {}
        for key in ("dc_io", "dc_tables", "dc_edges", "dc_profiles", "dc_queries"):
            required_tables[key] = require_table(
                issues, card_path, card_tables, TABLE_HEADERS[key]
            )
        validate_nonempty_table_cells(issues, card_path, card_tables)
        for key in ("dc_io", "dc_tables", "dc_profiles", "dc_queries"):
            if required_tables[key] and not required_tables[key][0].rows:
                issues.append(
                    Issue("ERROR", f"{dc_id} table {' | '.join(TABLE_HEADERS[key])} must contain at least one row", card_path)
                )

        card_resource_ids: set[str] = set()
        if resource_matches:
            for line, cells in resource_matches[0].rows:
                resource_id = cells[0].strip("`")
                if RESOURCE_ID_PATTERN.fullmatch(resource_id) is None:
                    issues.append(Issue("ERROR", f"invalid {dc_id} resource ID: {resource_id}", card_path, line))
                    continue
                if resource_id in card_resource_ids:
                    issues.append(Issue("ERROR", f"duplicate {dc_id} resource ID: {resource_id}", card_path, line))
                    continue
                card_resource_ids.add(resource_id)
                target = extract_link_target(cells[1])
                if target is None:
                    issues.append(Issue("ERROR", f"{dc_id} resource {resource_id} has no clickable file", card_path, line))
                    continue
                resolved = resolve_local_link(card_path, target)
                expected = resources.get(resource_id) or context_resources.get(resource_id)
                if expected is None:
                    issues.append(Issue("ERROR", f"{dc_id} references unregistered resource {resource_id}", card_path, line))
                elif resolved is not None and resolved != expected:
                    issues.append(Issue("ERROR", f"{dc_id} resource {resource_id} points to the wrong file: {resolved}", card_path, line))
        if missing := source_resources - card_resource_ids:
            issues.append(Issue("ERROR", f"{dc_id} source resources missing from card 引用入口: {sorted(missing)}", card_path))

        range_text = extract_section(card_text, "关联范围")
        card_rsus = expand_ids(range_text, "RSU")
        card_qs = expand_ids(range_text, "Q")
        if card_rsus != related_rsus:
            issues.append(
                Issue("ERROR", f"{dc_id} card/index RSU mismatch: card={sorted(card_rsus)}, index={sorted(related_rsus)}", card_path)
            )
        actual_rsus = {
            cells[0].strip("`")
            for _, cells in rsu_rows
            if dc_id in expand_ids(cells[5], "DC")
        }
        if actual_rsus != related_rsus:
            issues.append(
                Issue("ERROR", f"{dc_id} RSU dependency mismatch: map={sorted(actual_rsus)}, index={sorted(related_rsus)}", map_path)
            )
        for q_id in card_qs:
            if q_id not in q_ids:
                issues.append(Issue("ERROR", f"{dc_id} references undefined {q_id}", card_path))
        for fc_id in expand_ids(card_text, "FC"):
            if fc_id not in fc_ids:
                issues.append(Issue("ERROR", f"{dc_id} references undefined {fc_id}", card_path))
        for referenced_dc in expand_ids(card_text, "DC"):
            if referenced_dc not in indexed_ids:
                issues.append(Issue("ERROR", f"{dc_id} references undefined {referenced_dc}", card_path))

        table_ids: set[str] = set()
        if required_tables["dc_tables"]:
            for line, cells in required_tables["dc_tables"][0].rows:
                table_id = cells[0].strip("`")
                if not re.fullmatch(r"T-\d{3}", table_id):
                    issues.append(Issue("ERROR", f"invalid Table ID: {table_id}", card_path, line))
                elif table_id in table_ids:
                    issues.append(Issue("ERROR", f"duplicate Table ID: {table_id}", card_path, line))
                else:
                    table_ids.add(table_id)
        validate_sequence(issues, card_path, table_ids, "T")

        edge_ids: set[str] = set()
        if required_tables["dc_edges"]:
            for line, cells in required_tables["dc_edges"][0].rows:
                edge_id = cells[0].strip("`")
                if not re.fullmatch(r"E-\d{3}", edge_id):
                    issues.append(Issue("ERROR", f"invalid Edge ID: {edge_id}", card_path, line))
                elif edge_id in edge_ids:
                    issues.append(Issue("ERROR", f"duplicate Edge ID: {edge_id}", card_path, line))
                else:
                    edge_ids.add(edge_id)
                for endpoint in (cells[1].strip("`"), cells[2].strip("`")):
                    if re.fullmatch(r"T-\d{3}", endpoint) and endpoint not in table_ids:
                        issues.append(Issue("ERROR", f"{edge_id} references undefined table {endpoint}", card_path, line))
        validate_sequence(issues, card_path, edge_ids, "E")

        profile_ids: set[str] = set()
        if required_tables["dc_profiles"]:
            for line, cells in required_tables["dc_profiles"][0].rows:
                profile_id = cells[0].strip("`")
                if not re.fullmatch(r"DP-\d{3}", profile_id):
                    issues.append(Issue("ERROR", f"invalid Profile ID: {profile_id}", card_path, line))
                elif profile_id in profile_ids:
                    issues.append(Issue("ERROR", f"duplicate Profile ID: {profile_id}", card_path, line))
                else:
                    profile_ids.add(profile_id)
        validate_sequence(issues, card_path, profile_ids, "DP")

        gap_text = extract_section(card_text, "当前缺口")
        if status == "ready":
            if re.fullmatch(r"-\s*无[。；;]?", gap_text.strip()) is None:
                issues.append(Issue("ERROR", f"{dc_id} ready status requires 当前缺口 to be exactly '- 无'", card_path))
            if re.search(r"待确认|未知|未提供", card_text):
                issues.append(Issue("ERROR", f"{dc_id} ready card still contains unresolved data-contract wording", card_path))
        elif len(re.sub(r"\s+", "", gap_text)) < 8 or re.fullmatch(r"-\s*无[。；;]?", gap_text.strip()):
            issues.append(Issue("ERROR", f"{dc_id} {status} status requires a concrete current gap", card_path))

        if status == "blocked":
            captured = sorted(rsu_id for rsu_id in related_rsus if rsu_status.get(rsu_id) == "captured")
            if captured:
                issues.append(
                    Issue("ERROR", f"{dc_id} is blocked but related RSUs are captured: {captured}", map_path)
                )
            if not any(q_status.get(q_id) == "pending" for q_id in card_qs):
                issues.append(Issue("ERROR", f"{dc_id} blocked status requires at least one pending Q-ID", card_path))

    return len(indexed_ids)


def validate_sequence(issues: list[Issue], path: Path, ids: set[str], prefix: str) -> None:
    numbers = sorted(int(value.split("-")[1]) for value in ids)
    if not numbers:
        return
    expected = list(range(numbers[0], numbers[-1] + 1))
    if numbers != expected:
        issues.append(
            Issue(
                "WARN",
                f"{prefix} numbering has gaps; preserve gaps only when existing references require it",
                path,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate fixed module requirement preanalysis artifacts."
    )
    parser.add_argument(
        "preanalysis_dir",
        type=Path,
        help="Directory containing the preanalysis artifacts and manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Explicit preanalysis/v1 manifest. Defaults to <preanalysis-dir>/preanalysis-manifest.json.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Markdown file name to exclude from link checks. May be repeated.",
    )
    parser.add_argument(
        "--exclude-root",
        action="append",
        default=[],
        type=Path,
        help=(
            "Directory tree to exclude from Markdown link checks. Relative paths are "
            "resolved from preanalysis_dir. May be repeated."
        ),
    )
    parser.add_argument(
        "--require-canonical-layout",
        action="store_true",
        help="Require the directory to be <module-root>/preanalysis. Use for new scaffolds.",
    )
    args = parser.parse_args()

    module_dir = args.preanalysis_dir.resolve()
    issues: list[Issue] = []
    excluded_names = {"04-pilot-comparison-note.md", *args.exclude}

    if not module_dir.is_dir():
        print(f"ERROR: module directory does not exist: {module_dir}", file=sys.stderr)
        return 2

    excluded_roots: set[Path] = set()
    for raw_root in args.exclude_root:
        root = raw_root.resolve() if raw_root.is_absolute() else (module_dir / raw_root).resolve()
        try:
            relative = root.relative_to(module_dir)
        except ValueError:
            print(
                f"ERROR: excluded root must stay within preanalysis_dir: {root}",
                file=sys.stderr,
            )
            return 2
        if not relative.parts:
            print("ERROR: cannot exclude the entire preanalysis_dir", file=sys.stderr)
            return 2
        excluded_roots.add(root)

    try:
        layout = load_preanalysis_layout(module_dir, args.manifest)
    except ManifestError as exc:
        print(f"ERROR: invalid preanalysis manifest: {exc}", file=sys.stderr)
        return 1

    canonical_dir = (layout.module_root / CANONICAL_PREANALYSIS_DIR).resolve()
    if module_dir != canonical_dir:
        level = "ERROR" if args.require_canonical_layout else "WARN"
        issues.append(
            Issue(
                level,
                "non-canonical preanalysis layout; new artifacts must be stored in the direct "
                f"child directory {canonical_dir}",
                module_dir,
            )
        )
    if args.require_canonical_layout:
        if layout.manifest_path is None:
            issues.append(
                Issue(
                    "ERROR",
                    "canonical layout requires a preanalysis/v1 manifest",
                    module_dir,
                )
            )
        expected_output = (layout.module_root / "test-points").resolve()
        if layout.test_points_dir != expected_output:
            issues.append(
                Issue(
                    "ERROR",
                    "canonical layout requires output.test_points_dir to resolve to "
                    f"{expected_output}",
                    layout.manifest_path or module_dir,
                )
            )

    paths = layout.paths
    for name, path in paths.items():
        if not path.is_file():
            issues.append(Issue("ERROR", f"missing configured artifact: {name}", path))

    if any(not path.is_file() for path in paths.values()):
        for issue in issues:
            print(issue.render(module_dir))
        return 1

    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    analysis_paths = [
        paths["README.md"],
        paths["01-context-pack.md"],
        paths["02-sentence-test-point-map.md"],
        paths["03-clarification-questions.md"],
        paths["context-cards/README.md"],
        *sorted(paths["context-cards/README.md"].parent.glob("FC-*.md")),
    ]

    placeholder_pattern = re.compile(r"\{\{[A-Z0-9_]+\}\}")
    for path in analysis_paths:
        text = path.read_text(encoding="utf-8")
        require_single_h1(issues, path, text)
        for number, line in enumerate(text.splitlines(), start=1):
            if placeholder_pattern.search(line):
                issues.append(Issue("ERROR", "unresolved template placeholder", path, number))

    require_heading_order(issues, paths["README.md"], texts["README.md"], README_HEADINGS)
    require_heading_order(
        issues, paths["01-context-pack.md"], texts["01-context-pack.md"], CONTEXT_HEADINGS
    )
    require_heading_order(
        issues,
        paths["02-sentence-test-point-map.md"],
        texts["02-sentence-test-point-map.md"],
        MAP_HEADINGS,
    )
    require_heading_order(
        issues,
        paths["03-clarification-questions.md"],
        texts["03-clarification-questions.md"],
        QUESTION_HEADINGS,
    )
    require_heading_order(
        issues,
        paths["context-cards/README.md"],
        texts["context-cards/README.md"],
        ("卡片索引", "使用规则"),
    )

    context_h2 = [name for _, name in headings(texts["01-context-pack.md"])]
    boundary_candidates = [
        name
        for name in context_h2
        if name.endswith("边界")
        and name not in {"当前阶段边界", "已确认的理解边界", "原文、上下文和验证信息的边界"}
    ]
    if len(boundary_candidates) != 1:
        issues.append(
            Issue(
                "ERROR",
                f"expected exactly one domain contract boundary heading ending with '边界', found {len(boundary_candidates)}",
                paths["01-context-pack.md"],
            )
        )

    question_h2 = [name for _, name in headings(texts["03-clarification-questions.md"])]
    if not any(name.startswith("已确认的") for name in question_h2[3:-2]):
        issues.append(
            Issue("ERROR", "missing confirmed module logic summary section", paths["03-clarification-questions.md"])
        )

    readme_tables = extract_tables(texts["README.md"])
    context_tables = extract_tables(texts["01-context-pack.md"])
    map_tables = extract_tables(texts["02-sentence-test-point-map.md"])
    question_tables = extract_tables(texts["03-clarification-questions.md"])
    card_index_tables = extract_tables(texts["context-cards/README.md"])

    require_table(issues, paths["README.md"], readme_tables, TABLE_HEADERS["readme_files"])
    require_table(
        issues, paths["01-context-pack.md"], context_tables, TABLE_HEADERS["context_resources"]
    )
    require_table(
        issues, paths["01-context-pack.md"], context_tables, TABLE_HEADERS["context_boundary"]
    )
    rsu_tables = require_table(
        issues,
        paths["02-sentence-test-point-map.md"],
        map_tables,
        TABLE_HEADERS["rsu"],
        allow_multiple=True,
    )
    partition_tables = find_table(map_tables, TABLE_HEADERS["partition"])
    partition_heading_names = {
        name
        for level in (2, 3)
        for _, name in headings(texts["02-sentence-test-point-map.md"], level=level)
    }
    partition_section_present = "原文结构与拆分决策" in partition_heading_names
    if partition_section_present:
        partition_tables = require_table(
            issues,
            paths["02-sentence-test-point-map.md"],
            map_tables,
            TABLE_HEADERS["partition"],
        )
    elif not partition_tables:
        issues.append(
            Issue(
                "WARN",
                "legacy RSU map has no 原文结构与拆分决策 table; add it when this map is next maintained",
                paths["02-sentence-test-point-map.md"],
            )
        )
    else:
        issues.append(
            Issue(
                "ERROR",
                "partition decision table requires the ## 原文结构与拆分决策 section",
                paths["02-sentence-test-point-map.md"],
                partition_tables[0].line,
            )
        )
    coverage_tables = require_table(
        issues, paths["02-sentence-test-point-map.md"], map_tables, TABLE_HEADERS["coverage"]
    )
    answered_tables = require_table(
        issues, paths["03-clarification-questions.md"], question_tables, TABLE_HEADERS["answered_q"]
    )
    pending_tables = require_table(
        issues, paths["03-clarification-questions.md"], question_tables, TABLE_HEADERS["pending_q"]
    )
    card_tables = require_table(
        issues, paths["context-cards/README.md"], card_index_tables, TABLE_HEADERS["card_index"]
    )

    for path, tables in (
        (paths["README.md"], readme_tables),
        (paths["01-context-pack.md"], context_tables),
        (paths["02-sentence-test-point-map.md"], map_tables),
        (paths["03-clarification-questions.md"], question_tables),
        (paths["context-cards/README.md"], card_index_tables),
    ):
        validate_nonempty_table_cells(issues, path, tables)

    resources, resource_ids = parse_resource_table(
        issues, paths["02-sentence-test-point-map.md"], map_tables
    )
    context_resources, context_resource_ids = parse_context_resource_table(
        issues, paths["01-context-pack.md"], context_tables
    )
    global_id = layout.resource_roles["global_context"]
    module_requirement_id = layout.resource_roles["module_requirement"]
    module_context_id = layout.resource_roles["module_context"]

    for required_id in (module_requirement_id, global_id, module_context_id, "Q-INDEX"):
        if required_id not in resource_ids:
            issues.append(
                Issue("ERROR", f"map resource index is missing {required_id}", paths["02-sentence-test-point-map.md"])
            )

    for required_id in (module_requirement_id, global_id, "RSU-INDEX", "Q-INDEX"):
        if required_id not in context_resource_ids:
            issues.append(
                Issue("ERROR", f"Context Pack resource index is missing {required_id}", paths["01-context-pack.md"])
            )

    expected_resource_targets = {
        module_requirement_id: paths["00-module-requirement-pack.md"].resolve(),
        module_context_id: paths["01-context-pack.md"].resolve(),
        "Q-INDEX": paths["03-clarification-questions.md"].resolve(),
        "RSU-INDEX": paths["02-sentence-test-point-map.md"].resolve(),
        "FC-INDEX": paths["context-cards/README.md"].resolve(),
    }
    for resource_id, expected_target in expected_resource_targets.items():
        actual_target = resources.get(resource_id)
        if actual_target is not None and actual_target != expected_target:
            issues.append(
                Issue(
                    "ERROR",
                    f"resource {resource_id} points to the wrong file: {actual_target}",
                    paths["02-sentence-test-point-map.md"],
                )
            )

    expected_context_targets = {
        module_requirement_id: paths["00-module-requirement-pack.md"].resolve(),
        module_context_id: paths["01-context-pack.md"].resolve(),
        "Q-INDEX": paths["03-clarification-questions.md"].resolve(),
        "RSU-INDEX": paths["02-sentence-test-point-map.md"].resolve(),
        "FC-INDEX": paths["context-cards/README.md"].resolve(),
    }
    if global_id in resources:
        expected_context_targets[global_id] = resources[global_id]
    for resource_id, expected_target in expected_context_targets.items():
        actual_target = context_resources.get(resource_id)
        if actual_target is not None and actual_target != expected_target:
            issues.append(
                Issue(
                    "ERROR",
                    f"Context Pack resource {resource_id} points to the wrong file: {actual_target}",
                    paths["01-context-pack.md"],
                )
            )

    rsu_rows = [row for table in rsu_tables for row in table.rows]
    if not rsu_rows:
        issues.append(Issue("ERROR", "RSU mapping has no rows", paths["02-sentence-test-point-map.md"]))
    rsu_ids: set[str] = set()
    for line, cells in rsu_rows:
        rsu_id = cells[0].strip("`")
        if not re.fullmatch(r"RSU-\d{3}", rsu_id):
            issues.append(Issue("ERROR", f"invalid RSU ID: {rsu_id}", paths["02-sentence-test-point-map.md"], line))
            continue
        if rsu_id in rsu_ids:
            issues.append(Issue("ERROR", f"duplicate RSU ID: {rsu_id}", paths["02-sentence-test-point-map.md"], line))
        rsu_ids.add(rsu_id)
        if cells[7].strip("`") not in RSU_STATUSES:
            issues.append(
                Issue("ERROR", f"invalid RSU status: {cells[7]}", paths["02-sentence-test-point-map.md"], line)
            )
        source_id = cells[3].strip("`")
        if not source_id.startswith("SRC-"):
            issues.append(
                Issue("ERROR", f"RSU source must use a SRC-* resource: {source_id}", paths["02-sentence-test-point-map.md"], line)
            )
        if source_id not in resource_ids:
            issues.append(
                Issue("ERROR", f"undefined RSU source resource: {source_id}", paths["02-sentence-test-point-map.md"], line)
            )
        if not cells[4].strip() or cells[4].strip() == "无":
            issues.append(Issue("ERROR", f"{rsu_id} has no semantic source location", paths["02-sentence-test-point-map.md"], line))

    validate_sequence(issues, paths["02-sentence-test-point-map.md"], rsu_ids, "RSU")

    partition_rows = validate_partition_decisions(
        issues,
        paths["02-sentence-test-point-map.md"],
        partition_tables,
        rsu_ids,
        resource_ids,
    )
    validate_rsu_source_shape(
        issues,
        paths["02-sentence-test-point-map.md"],
        rsu_rows,
    )

    coverage_rows = [row for table in coverage_tables for row in table.rows]
    if not coverage_rows:
        issues.append(Issue("ERROR", "source coverage table has no rows", paths["02-sentence-test-point-map.md"]))
    seen_coverage_scopes: set[tuple[str, str] | tuple[str, str, int]] = set()
    for line, cells in coverage_rows:
        source_scope = cells[0].strip("`").strip()
        scope_key = parse_source_scope(cells[0])
        if scope_key is None:
            issues.append(
                Issue(
                    "ERROR",
                    "source coverage scope must use 'SRC-ID > semantic location'",
                    paths["02-sentence-test-point-map.md"],
                    line,
                )
            )
        elif scope_key[0] not in resource_ids:
            issues.append(
                Issue(
                    "ERROR",
                    f"source coverage references undefined resource: {scope_key[0]}",
                    paths["02-sentence-test-point-map.md"],
                    line,
                )
            )
        comparable_scope = scope_key or ("INVALID", source_scope, line)
        if comparable_scope in seen_coverage_scopes:
            issues.append(
                Issue(
                    "ERROR",
                    f"duplicate source coverage scope: {source_scope}",
                    paths["02-sentence-test-point-map.md"],
                    line,
                )
            )
        seen_coverage_scopes.add(comparable_scope)
        status = cells[1].strip("`")
        if status not in COVERAGE_STATUSES:
            issues.append(Issue("ERROR", f"invalid coverage status: {status}", paths["02-sentence-test-point-map.md"], line))

    answered_rows = [row for table in answered_tables for row in table.rows]
    pending_rows = [row for table in pending_tables for row in table.rows]
    q_rows = [*answered_rows, *pending_rows]
    q_ids: set[str] = set()
    for section_name, rows, allowed_statuses in (
        ("已确认问题与结论", answered_rows, {"answered", "out-of-scope"}),
        ("待确认问题", pending_rows, {"pending", "deferred"}),
    ):
        for line, cells in rows:
            q_id = cells[0].strip("`")
            if not re.fullmatch(r"Q-\d{3}", q_id):
                issues.append(Issue("ERROR", f"invalid Q ID: {q_id}", paths["03-clarification-questions.md"], line))
                continue
            if q_id in q_ids:
                issues.append(Issue("ERROR", f"duplicate Q ID: {q_id}", paths["03-clarification-questions.md"], line))
            q_ids.add(q_id)
            status = cells[2].strip("`")
            if status not in Q_STATUSES or status not in allowed_statuses:
                issues.append(
                    Issue(
                        "ERROR",
                        f"status {status} is not allowed in section {section_name}",
                        paths["03-clarification-questions.md"],
                        line,
                    )
                )
            if not cells[3].strip() or not cells[4].strip():
                detail = "conclusion or backfill result" if section_name == "已确认问题与结论" else "question or pending handling"
                issues.append(Issue("ERROR", f"{q_id} has no {detail}", paths["03-clarification-questions.md"], line))

    validate_sequence(issues, paths["03-clarification-questions.md"], q_ids, "Q")
    validate_partition_coverage_consistency(
        issues,
        paths["02-sentence-test-point-map.md"],
        partition_rows,
        coverage_rows,
        {cells[0].strip("`"): cells[2].strip("`") for _, cells in q_rows},
    )

    fc_files = sorted(paths["context-cards/README.md"].parent.glob("FC-*.md"))
    fc_ids: set[str] = set()
    fc_paths: dict[str, Path] = {}
    for path in fc_files:
        match = re.match(r"(FC-\d{3})-", path.name)
        if not match:
            issues.append(Issue("ERROR", "Context Card filename must start with FC-xxx-", path))
            continue
        fc_id = match.group(1)
        if fc_id in fc_ids:
            issues.append(Issue("ERROR", f"duplicate FC ID: {fc_id}", path))
        fc_ids.add(fc_id)
        fc_paths[fc_id] = path.resolve()
        text = path.read_text(encoding="utf-8")
        first_heading = next((name for _, name in headings(text, level=1)), "")
        if not first_heading.startswith(fc_id):
            issues.append(Issue("ERROR", f"H1 must start with {fc_id}", path, 1))
        h2_names = {name for _, name in headings(text)}
        for required_heading in ("引用入口", "关联来源"):
            if required_heading not in h2_names:
                issues.append(Issue("ERROR", f"missing Context Card heading: ## {required_heading}", path))
        if not any(name in h2_names for name in ("当前边界", "当前范围", "当前明确不验证", "不在本卡片展开")):
            issues.append(Issue("ERROR", "Context Card has no explicit boundary section", path))

    validate_sequence(issues, paths["context-cards/README.md"], fc_ids, "FC")

    card_rows = [row for table in card_tables for row in table.rows]
    indexed_cards: dict[str, Path] = {}
    for line, cells in card_rows:
        card_id = cells[0].strip("`")
        if not re.fullmatch(r"FC-\d{3}", card_id):
            issues.append(Issue("ERROR", f"invalid Context Card index ID: {card_id}", paths["context-cards/README.md"], line))
            continue
        if card_id in indexed_cards:
            issues.append(Issue("ERROR", f"duplicate Context Card index ID: {card_id}", paths["context-cards/README.md"], line))
            continue
        target = extract_link_target(cells[2])
        if target is None:
            issues.append(Issue("ERROR", f"Context Card index {card_id} has no clickable file", paths["context-cards/README.md"], line))
            continue
        resolved = resolve_local_link(paths["context-cards/README.md"], target)
        if resolved is not None:
            indexed_cards[card_id] = resolved

    if not fc_ids and "当前无 Context Card" not in texts["context-cards/README.md"]:
        issues.append(Issue("ERROR", "empty Context Card index must state '当前无 Context Card'", paths["context-cards/README.md"]))
    if fc_ids and "当前无 Context Card" in texts["context-cards/README.md"]:
        issues.append(Issue("ERROR", "Context Card index claims empty while FC files exist", paths["context-cards/README.md"]))

    for fc_id, fc_path in fc_paths.items():
        indexed_path = indexed_cards.get(fc_id)
        if indexed_path is None:
            issues.append(Issue("ERROR", f"{fc_id} is missing from the Context Card index", paths["context-cards/README.md"]))
        elif indexed_path != fc_path:
            issues.append(Issue("ERROR", f"{fc_id} index points to the wrong file: {indexed_path}", paths["context-cards/README.md"]))
        map_path = resources.get(fc_id)
        if fc_id not in resource_ids:
            issues.append(Issue("ERROR", f"{fc_id} is missing from the map resource index", paths["02-sentence-test-point-map.md"]))
        elif map_path is not None and map_path != fc_path:
            issues.append(Issue("ERROR", f"map resource {fc_id} points to the wrong file: {map_path}", paths["02-sentence-test-point-map.md"]))

    for card_id in indexed_cards:
        if card_id not in fc_ids:
            issues.append(Issue("ERROR", f"Context Card index references missing file for {card_id}", paths["context-cards/README.md"]))

    for resource_id in sorted(resource_ids):
        if re.fullmatch(r"FC-\d{3}", resource_id) and resource_id not in fc_ids:
            issues.append(
                Issue("ERROR", f"map resource index references missing Context Card for {resource_id}", paths["02-sentence-test-point-map.md"])
            )

    for resource_id in sorted(context_resource_ids):
        if not re.fullmatch(r"FC-\d{3}", resource_id):
            continue
        if resource_id not in fc_ids:
            issues.append(
                Issue("ERROR", f"Context Pack resource index references missing Context Card for {resource_id}", paths["01-context-pack.md"])
            )
            continue
        actual_target = context_resources.get(resource_id)
        expected_target = fc_paths[resource_id]
        if actual_target is not None and actual_target != expected_target:
            issues.append(
                Issue(
                    "ERROR",
                    f"Context Pack resource {resource_id} points to the wrong file: {actual_target}",
                    paths["01-context-pack.md"],
                )
            )

    dc_count = validate_data_closures(
        issues,
        module_dir,
        paths["02-sentence-test-point-map.md"],
        paths["01-context-pack.md"],
        resources,
        resource_ids,
        context_resources,
        context_resource_ids,
        rsu_rows,
        rsu_ids,
        q_rows,
        q_ids,
        fc_ids,
    )

    covered_rsu_ids: set[str] = set()
    for line, cells in coverage_rows:
        referenced_rsus = expand_ids(cells[2], "RSU")
        referenced_qs = expand_ids(cells[2], "Q")
        covered_rsu_ids.update(referenced_rsus)
        for rsu_id in referenced_rsus:
            if rsu_id not in rsu_ids:
                issues.append(Issue("ERROR", f"coverage table references undefined {rsu_id}", paths["02-sentence-test-point-map.md"], line))
        for q_id in referenced_qs:
            if q_id not in q_ids:
                issues.append(Issue("ERROR", f"coverage table references undefined {q_id}", paths["02-sentence-test-point-map.md"], line))
        if cells[1].strip("`") == "mapped" and not referenced_rsus:
            issues.append(Issue("ERROR", "mapped coverage row must reference at least one RSU", paths["02-sentence-test-point-map.md"], line))
    for rsu_id in sorted(rsu_ids - covered_rsu_ids):
        issues.append(Issue("ERROR", f"{rsu_id} is missing from the source coverage table", paths["02-sentence-test-point-map.md"]))

    for line, cells in rsu_rows:
        rsu_id = cells[0].strip("`")
        for q_id in expand_ids(cells[6], "Q"):
            if q_id not in q_ids:
                issues.append(Issue("ERROR", f"{rsu_id} references undefined {q_id}", paths["02-sentence-test-point-map.md"], line))
        for fc_id in expand_ids(cells[5], "FC"):
            if fc_id not in fc_ids:
                issues.append(Issue("ERROR", f"{rsu_id} references undefined {fc_id}", paths["02-sentence-test-point-map.md"], line))
        for dc_id in expand_ids(cells[5], "DC"):
            if dc_id not in resource_ids:
                issues.append(Issue("ERROR", f"{rsu_id} references undefined {dc_id}", paths["02-sentence-test-point-map.md"], line))
        for source_id in re.findall(r"SRC-[A-Z0-9-]+", cells[5]):
            if source_id not in resource_ids:
                issues.append(Issue("ERROR", f"{rsu_id} references undefined resource {source_id}", paths["02-sentence-test-point-map.md"], line))

    for line, cells in q_rows:
        q_id = cells[0].strip("`")
        for rsu_id in expand_ids(cells[1], "RSU"):
            if rsu_id not in rsu_ids:
                issues.append(Issue("ERROR", f"{q_id} references undefined {rsu_id}", paths["03-clarification-questions.md"], line))
        for fc_id in expand_ids(cells[1], "FC"):
            if fc_id not in fc_ids:
                issues.append(Issue("ERROR", f"{q_id} references undefined {fc_id}", paths["03-clarification-questions.md"], line))
        for dc_id in expand_ids(cells[1], "DC"):
            if dc_id not in resource_ids:
                issues.append(Issue("ERROR", f"{q_id} references undefined {dc_id}", paths["03-clarification-questions.md"], line))

    for path in fc_files:
        text = path.read_text(encoding="utf-8")
        for rsu_id in expand_ids(text, "RSU"):
            if rsu_id not in rsu_ids:
                issues.append(Issue("ERROR", f"Context Card references undefined {rsu_id}", path))
        for q_id in expand_ids(text, "Q"):
            if q_id not in q_ids:
                issues.append(Issue("ERROR", f"Context Card references undefined {q_id}", path))
        for dc_id in expand_ids(text, "DC"):
            if dc_id not in resource_ids:
                issues.append(Issue("ERROR", f"Context Card references undefined {dc_id}", path))

    for path_key in ("README.md", "01-context-pack.md", "02-sentence-test-point-map.md"):
        validate_fixed_inputs(issues, paths[path_key], texts[path_key], layout.resource_roles)

    context_text = texts["01-context-pack.md"]
    if "### 主链路" not in context_text or "### 逻辑说明" not in context_text:
        issues.append(Issue("ERROR", "detailed logic must contain main flow and numbered explanation", paths["01-context-pack.md"]))

    forbidden_map_headers = {
        "ATP-ID",
        "STP-ID",
        "复杂度",
        "处理模式",
        "测试项",
        "测试意图",
        "测试步骤",
        "预期结果",
        "TP-ID",
    }
    for table in map_tables:
        overlap = forbidden_map_headers.intersection(table.headers)
        if overlap:
            issues.append(Issue("ERROR", f"map contains forbidden columns: {', '.join(sorted(overlap))}", paths["02-sentence-test-point-map.md"], table.line))

    for path in module_dir.iterdir():
        if path.is_dir() and path.name.startswith("test-point-batch-"):
            issues.append(Issue("ERROR", "test-point batch directory is outside this stage", path))

    checked_links, broken_links = validate_links(
        issues,
        module_dir,
        excluded_names,
        excluded_roots,
    )
    source_checked, source_skipped = validate_source_match(
        issues, paths["02-sentence-test-point-map.md"], rsu_rows, resources
    )

    errors = [issue for issue in issues if issue.level == "ERROR"]
    warnings = [issue for issue in issues if issue.level == "WARN"]
    for issue in issues:
        print(issue.render(module_dir))

    print(
        "Validation summary: "
        f"errors={len(errors)}, warnings={len(warnings)}, "
        f"manifest={'preanalysis/v1' if layout.manifest_path else 'legacy'}, "
        f"markdown_links={checked_links}, broken_links={broken_links}, "
        f"rsu={len(rsu_ids)}, q={len(q_ids)}, fc={len(fc_ids)}, dc={dc_count}, "
        f"source_matches_checked={source_checked}, source_matches_skipped={source_skipped}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
