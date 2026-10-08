#!/usr/bin/env python3
"""Create the canonical module preanalysis skeleton without inventing requirement text."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import quote


TEMPLATE_FILES = {
    "README.md.tmpl": "README.md",
    "01-context-pack.md.tmpl": "01-context-pack.md",
    "02-sentence-test-point-map.md.tmpl": "02-sentence-test-point-map.md",
    "03-clarification-questions.md.tmpl": "03-clarification-questions.md",
    "context-cards/README.md.tmpl": "context-cards/README.md",
}
DATA_CLOSURE_TEMPLATE_FILES = {
    "data-closures/README.md.tmpl": "data-closures/README.md",
    "data-closures/DC-card.md.tmpl": "data-closures/DC-001-数据闭包.md",
}
MANIFEST_NAME = "preanalysis-manifest.json"
MANIFEST_ARTIFACTS = {
    "readme": "README.md",
    "module_requirement": "00-module-requirement-pack.md",
    "context_pack": "01-context-pack.md",
    "rsu_map": "02-sentence-test-point-map.md",
    "clarifications": "03-clarification-questions.md",
    "context_card_index": "context-cards/README.md",
}
RESOURCE_ROLES = {
    "global_context": "SRC-GLOBAL",
    "module_requirement": "SRC-MOD",
    "module_context": "CTX",
}
CANONICAL_PREANALYSIS_DIR = "preanalysis"
FLAT_LAYOUT_MARKERS = (
    MANIFEST_NAME,
    "01-context-pack.md",
    "02-sentence-test-point-map.md",
    "03-clarification-questions.md",
    "context-cards",
    "data-closures",
)


def find_global_context(module_dir: Path) -> Path | None:
    for parent in (module_dir, *module_dir.parents):
        for relative in ("global/project-context.md", "00-global/00-project-context.md"):
            candidate = parent / relative
            if candidate.is_file():
                return candidate
    return None


def relative_markdown_path(source_file: Path, target_file: Path) -> str:
    relative = os.path.relpath(target_file, start=source_file.parent)
    return Path(relative).as_posix()


def relative_markdown_link(source_file: Path, target_file: Path) -> str:
    # JSON paths remain filesystem paths; only Markdown targets are URI-encoded.
    return quote(relative_markdown_path(source_file, target_file), safe="/")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create fixed module requirement preanalysis files from bundled templates."
    )
    parser.add_argument(
        "target_dir",
        type=Path,
        help=(
            "Module workspace root. New scaffolds are written to "
            "<module-root>/preanalysis by default."
        ),
    )
    parser.add_argument(
        "--module-root",
        type=Path,
        help=(
            "Compatibility mode for the former CLI: treat target_dir as the preanalysis "
            "directory and this value as the module root. Do not use for new scaffolds."
        ),
    )
    parser.add_argument(
        "--test-points-dir",
        type=Path,
        help="Default RSU test-point output directory. Defaults to <module-root>/test-points.",
    )
    parser.add_argument("--module-name", help="Display name used in Markdown headings.")
    parser.add_argument("--global-context", type=Path)
    parser.add_argument(
        "--requirement-source",
        type=Path,
        help="Copy this source verbatim to 00-module-requirement-pack.md when it is missing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite generated analysis skeletons. Never overwrites the module requirement pack.",
    )
    parser.add_argument(
        "--refresh-manifest",
        action="store_true",
        help="Rewrite only the canonical manifest routing values without requiring --force.",
    )
    parser.add_argument(
        "--with-data-closures",
        action="store_true",
        help="Also scaffold the optional DC-INDEX/DC-001 data-closure contract for database-relevant modules.",
    )
    parser.add_argument(
        "--data-closure-title",
        default="核心业务数据链路",
        help="Display title for the initial DC-001 skeleton.",
    )
    parser.add_argument(
        "--data-source-id",
        default="SRC-DB-SCHEMA",
        help="Initial schema/SQL/code resource ID referenced by the DC-001 skeleton.",
    )
    parser.add_argument(
        "--data-source",
        type=Path,
        help="Schema, SQL, code, or design source used by the initial DC-001 skeleton.",
    )
    args = parser.parse_args()

    target_dir = args.target_dir.resolve()
    compatibility_mode = args.module_root is not None
    if compatibility_mode:
        preanalysis_dir = target_dir
        module_root = args.module_root.resolve()
        print(
            "WARN: using the former CLI compatibility mode; new scaffolds must pass the module "
            "root as target_dir and use its preanalysis child directory.",
            file=sys.stderr,
        )
    else:
        module_root = target_dir
        preanalysis_dir = (module_root / CANONICAL_PREANALYSIS_DIR).resolve()

    if not module_root.is_dir():
        print(f"ERROR: module root does not exist: {module_root}", file=sys.stderr)
        return 2
    if not compatibility_mode and preanalysis_dir.parent != module_root:
        print(
            "ERROR: preanalysis directory must be a direct child of the module root so the "
            f"downstream skill can auto-discover its manifest: {preanalysis_dir}",
            file=sys.stderr,
        )
        return 2
    if not compatibility_mode:
        flat_markers = [name for name in FLAT_LAYOUT_MARKERS if (module_root / name).exists()]
        if flat_markers:
            print(
                "ERROR: existing legacy flat preanalysis layout detected in the module root "
                f"({', '.join(flat_markers)}). Refusing to create a second manifest under "
                f"{preanalysis_dir}. Maintain the legacy layout with the former compatibility "
                "form or migrate it as an explicit, link-aware task.",
                file=sys.stderr,
            )
            return 2
    try:
        preanalysis_dir.relative_to(module_root)
    except ValueError:
        print(
            f"ERROR: preanalysis directory must be inside module root: {preanalysis_dir} not under {module_root}",
            file=sys.stderr,
        )
        return 2
    test_points_dir = (
        args.test_points_dir.resolve() if args.test_points_dir else module_root / "test-points"
    )
    try:
        relative_output = test_points_dir.relative_to(module_root)
    except ValueError:
        print(
            f"ERROR: test-points directory must be inside module root: {test_points_dir}",
            file=sys.stderr,
        )
        return 2
    if not relative_output.parts:
        print("ERROR: test-points directory cannot be the module root itself", file=sys.stderr)
        return 2
    module_name = args.module_name or module_root.name

    # Validate all requested input paths before creating even a partial scaffold.
    global_context = (
        args.global_context.resolve() if args.global_context else find_global_context(module_root)
    )
    if global_context is None or not global_context.is_file():
        print("ERROR: global context not found. Pass --global-context <project-context.md>.", file=sys.stderr)
        return 2
    if args.with_data_closures and (args.data_source is None or not args.data_source.resolve().is_file()):
        print("ERROR: --with-data-closures requires an existing --data-source.", file=sys.stderr)
        return 2

    requirement_pack = preanalysis_dir / "00-module-requirement-pack.md"
    if not requirement_pack.exists():
        if args.requirement_source is None:
            print(
                "ERROR: 00-module-requirement-pack.md is missing. Provide --requirement-source; "
                "the scaffold will not invent requirement text.",
                file=sys.stderr,
            )
            return 2
        source = args.requirement_source.resolve()
        if not source.is_file():
            print(f"ERROR: requirement source does not exist: {source}", file=sys.stderr)
            return 2
        preanalysis_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, requirement_pack)
        print(f"created {requirement_pack} from {source}")

    template_root = Path(__file__).resolve().parent.parent / "assets" / "templates"
    created = 0
    skipped = 0

    template_files = dict(TEMPLATE_FILES)
    if args.with_data_closures:
        if args.data_source is None:
            print(
                "ERROR: --with-data-closures requires --data-source; the scaffold will not invent database structure.",
                file=sys.stderr,
            )
            return 2
        data_source = args.data_source.resolve()
        if not data_source.is_file():
            print(f"ERROR: data source does not exist: {data_source}", file=sys.stderr)
            return 2
        template_files.update(DATA_CLOSURE_TEMPLATE_FILES)
    else:
        data_source = None

    for template_name, output_name in template_files.items():
        template = template_root / template_name
        output = preanalysis_dir / output_name
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and not args.force:
            print(f"skip existing {output}")
            skipped += 1
            continue

        text = template.read_text(encoding="utf-8")
        global_link = relative_markdown_link(output, global_context)
        text = text.replace("{{MODULE_NAME}}", module_name)
        text = text.replace("{{GLOBAL_CONTEXT_LINK}}", global_link)
        data_source_link = (
            relative_markdown_link(output, data_source) if data_source is not None else ""
        )
        replacements = {
            "{{DATA_CLOSURE_FILE_ROLE}}": (
                "| `data-closures/` | 可复用的最小业务数据路径、表角色、连接/过滤、准备、查询和清理契约 |"
                if args.with_data_closures
                else ""
            ),
            "{{DATA_CLOSURE_QUICK_INDEX}}": (
                "- [Data Closures](./data-closures/README.md)"
                if args.with_data_closures
                else ""
            ),
            "{{DATA_CLOSURE_CONTEXT_RESOURCES}}": (
                "| DC-INDEX | [Data Closures](./data-closures/README.md) | 数据闭包索引和状态 |\n"
                "| DC-001 | [核心数据闭包](./data-closures/DC-001-数据闭包.md) | 初始业务数据路径 |"
                if args.with_data_closures
                else ""
            ),
            "{{DATA_CLOSURE_MAP_RESOURCES}}": (
                "| DC-INDEX | [Data Closures](./data-closures/README.md) | 数据闭包索引和状态 |\n"
                "| DC-001 | [核心数据闭包](./data-closures/DC-001-数据闭包.md) | 初始业务数据路径 |\n"
                f"| {args.data_source_id} | [数据库或实现依据]({data_source_link}) | 表结构、查询或实现证据 |"
                if args.with_data_closures
                else ""
            ),
            "{{RSU_RELATED_CONTEXT}}": "CTX、DC-001" if args.with_data_closures else "CTX",
            "{{RSU_STATUS}}": "pending-context" if args.with_data_closures else "captured",
            "{{PARTITION_DECISION_REASON}}": "待基于真实需求原文完成语义闭合审查；此行仅为结构占位，不代表已确认的 RSU 判定。",
            "{{DATA_CLOSURE_TITLE}}": args.data_closure_title,
            "{{DATA_SOURCE_ID}}": args.data_source_id,
            "{{DATA_SOURCE_IDS}}": args.data_source_id,
            "{{DATA_SOURCE_LINK}}": data_source_link,
        }
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, value)
        output.write_text(text, encoding="utf-8", newline="\n")
        print(f"created {output}")
        created += 1

    manifest_path = preanalysis_dir / MANIFEST_NAME
    if manifest_path.exists() and not (args.force or args.refresh_manifest):
        print(f"skip existing {manifest_path}")
        skipped += 1
    else:
        manifest = {
            "schema_version": "preanalysis/v1",
            "module_root": relative_markdown_path(manifest_path, module_root),
            "artifacts": dict(MANIFEST_ARTIFACTS),
            "resource_roles": dict(RESOURCE_ROLES),
            "output": {
                "test_points_dir": relative_markdown_path(manifest_path, test_points_dir),
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"created {manifest_path}")
        created += 1

    print(
        f"scaffold complete: created={created}, skipped={skipped}. "
        f"preanalysis_dir={preanalysis_dir}. "
        "Replace every {{...}} placeholder before final validation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
