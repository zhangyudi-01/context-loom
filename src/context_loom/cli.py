from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .assembly import assemble
from .baseline import compile_baseline
from .config import load_config
from .execution import prepare_next, submit_result
from .io import read_json, write_json_atomic
from .planning import build_plan
from .state import load_or_create


def _workflow(path: str) -> tuple[Path, dict[str, Any]]:
    directory = Path(path).resolve()
    return directory, load_config(directory)


def _cmd_init(args: argparse.Namespace) -> int:
    directory = Path(args.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    config = {
        "schema_version": "context-loom/workflow-v1",
        "workflow_id": args.workflow_id,
        "root": ".",
        "sources": [{"source_id": "SOURCE-001", "path": "source.md", "role": "context"}],
        "tasks": [{"task_id": "TASK-001", "title": "Example task", "complexity": "simple", "payload": {}}],
        "policy": {},
    }
    write_json_atomic(directory / "context-loom.json", config)
    (directory / "source.md").write_text("Replace this with an authoritative source.\n", encoding="utf-8")
    print(f"created {directory / 'context-loom.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="context-loom", description="Focused AI workflow control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("directory")
    init.add_argument("--workflow-id", default="demo")
    init.set_defaults(fn=_cmd_init)
    for name in ("compile", "plan", "prepare-next", "assemble", "status"):
        command = sub.add_parser(name)
        command.add_argument("directory")
        command.set_defaults(fn=lambda args, name=name: _run(name, args.directory))
    submit = sub.add_parser("submit")
    submit.add_argument("directory")
    submit.add_argument("--result", required=True)
    submit.set_defaults(fn=lambda args: _run("submit", args.directory, args.result))
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"context-loom: error: {exc}\n")


def _run(command: str, directory_arg: str, result_path: str | None = None) -> int:
    directory, config = _workflow(directory_arg)
    if command == "compile":
        baseline = compile_baseline(directory, config)
        print(json.dumps(baseline.to_dict(), ensure_ascii=False, indent=2))
        return 0
    baseline = read_json(directory / ".context-loom" / "baseline.json")
    if command == "plan":
        plan = build_plan(directory, config, baseline)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    plan = read_json(directory / ".context-loom" / "plan.json")
    if command == "prepare-next":
        packet = prepare_next(directory, config, baseline, plan)
        print("NO_PENDING_BATCH" if packet is None else json.dumps(packet, ensure_ascii=False, indent=2))
        return 0
    if command == "submit":
        result = read_json(Path(result_path).resolve())
        print(json.dumps(submit_result(directory, config, result), ensure_ascii=False))
        return 0
    if command == "assemble":
        print(assemble(directory, config, plan))
        return 0
    print(json.dumps(load_or_create(directory, str(config["workflow_id"])), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

