from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .assembly import assemble
from .baseline import compile_baseline
from .config import load_config
from .execution import prepare_next, submit_result, retry_failed
from .io import read_json, write_json_atomic
from .planning import build_plan
from .state import load_or_create
from .agents import CodexHost
from .orchestrator import run
from .config import resolve_root
from .testing_setup import setup_test_points
from .testing_points import TestPointAdapter
from .testing_cases import TestCaseAdapter
from .testing_full import setup_full, run_full


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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="context-loom", description="Focused AI workflow control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("directory")
    init.add_argument("--workflow-id", default="demo")
    init.set_defaults(fn=_cmd_init)
    setup = sub.add_parser("setup-testing", help="Create a separate RSU test-point pilot from existing preanalysis")
    setup.add_argument("--module", required=True)
    setup.add_argument("--output", required=True)
    setup.add_argument("--rsu", nargs="+", required=True)
    setup.set_defaults(fn=lambda args: _cmd_setup_testing(args))
    full_setup = sub.add_parser("setup-testing-full", help="Snapshot a source module into a separate end-to-end trial")
    full_setup.add_argument("--module", required=True)
    full_setup.add_argument("--output", required=True)
    full_setup.set_defaults(fn=lambda args: print(setup_full(Path(args.module), Path(args.output))) or 0)
    full_run = sub.add_parser("run-testing-full", help="Resume fresh RSU discovery, all test points and all cases")
    full_run.add_argument("directory")
    full_run.add_argument("--binary", default="codex")
    full_run.add_argument("--timeout", type=int, default=1800)
    full_run.set_defaults(fn=lambda args: print(run_full(Path(args.directory),
        lambda path: CodexHost(path, binary=args.binary, timeout=args.timeout))) or 0)
    doctor = sub.add_parser("doctor", help="Validate sources and optional Codex CLI without model calls or writes")
    doctor.add_argument("directory")
    doctor.add_argument("--offline", action="store_true", help="Skip the optional Codex CLI capability check")
    doctor.set_defaults(fn=lambda args: _cmd_doctor(args))
    for name in ("compile", "plan", "prepare-next", "assemble", "status"):
        command = sub.add_parser(name)
        command.add_argument("directory")
        command.set_defaults(fn=lambda args, name=name: _run(name, args.directory))
    submit = sub.add_parser("submit")
    submit.add_argument("directory")
    submit.add_argument("--result", required=True)
    submit.set_defaults(fn=lambda args: _run("submit", args.directory, args.result))
    automatic = sub.add_parser("run", help="Run the full AI workflow with real baseline forks (may incur model costs)")
    automatic.add_argument("directory")
    automatic.add_argument("--binary", default="codex")
    automatic.add_argument("--timeout", type=int, default=1800)
    automatic.set_defaults(fn=lambda args: _run_agent(args))
    retry = sub.add_parser("retry-failed", help="Explicitly requeue a failed task, preserving the failed attempt")
    retry.add_argument("directory")
    retry.add_argument("--task-id", required=True)
    retry.set_defaults(fn=lambda args: _run_retry(args))
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"context-loom: error: {exc}\n")


def _run(command: str, directory_arg: str, result_path: str | None = None) -> int:
    directory, config = _workflow(directory_arg)
    if command == "compile":
        baseline = compile_baseline(directory, config)
        print(json.dumps({"baseline_id": baseline.baseline_id,
                          "source_fingerprint": baseline.source_fingerprint,
                          "sources": len(baseline.sources),
                          "file": str(directory / ".context-loom" / "baseline.json")},
                         ensure_ascii=False, indent=2))
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


def _run_agent(args: argparse.Namespace) -> int:
    directory, config = _workflow(args.directory)
    adapters = {"testing-test-points": TestPointAdapter, "testing-test-cases": TestCaseAdapter}
    adapter = adapters[config["domain"]]() if config.get("domain") in adapters else None
    if config.get("domain") not in (None, *adapters):
        raise ValueError(f"unsupported workflow domain: {config['domain']}")
    _check_sources(directory, config)
    print(run(directory, config, CodexHost(directory, binary=args.binary, timeout=args.timeout), adapter))
    return 0


def _cmd_setup_testing(args: argparse.Namespace) -> int:
    print(setup_test_points(Path(args.module), Path(args.output), args.rsu))
    return 0


def _check_sources(directory: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    root = resolve_root(directory, config)
    items = []
    for entry in (config.get("sources") or []) + (config.get("contexts") or []):
        relative = str(entry.get("path", ""))
        path = (root / relative).resolve()
        if not relative or not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"missing or out-of-bounds source: {relative}")
        items.append({"id": entry.get("source_id", entry.get("context_id")),
                      "bytes": path.stat().st_size, "path": relative})
    if not any(source.get("source_id") for source in config.get("sources", [])):
        raise ValueError("at least one authoritative source is required")
    return items


def _cmd_doctor(args: argparse.Namespace) -> int:
    directory, config = _workflow(args.directory)
    items = _check_sources(directory, config)
    if not args.offline:
        CodexHost(directory)  # Capability check only: does not make a model call.
    print(json.dumps({"status": "ready", "workflow_id": config["workflow_id"],
                      "task_count": len(config.get("tasks", [])), "sources": items,
                      "codex_cli": "not_checked" if args.offline else "supports_exec_fork",
                      "note": "Model authentication and output quality are not checked; run incurs model costs."},
                     ensure_ascii=False, indent=2))
    return 0


def _run_retry(args: argparse.Namespace) -> int:
    directory, config = _workflow(args.directory)
    retry_failed(directory, config, args.task_id)
    print(f"requeued {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
