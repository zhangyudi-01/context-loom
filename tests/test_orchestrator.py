from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from context_loom.agents import AgentTurn, CodexHost
from context_loom.discovery import validate_discovery
from context_loom.orchestrator import run
from context_loom.state import load_or_create
from context_loom.execution import retry_failed
from context_loom.assembly import assemble
from context_loom.io import read_json
from context_loom.audit import AUDIT_NAME, InvocationAudit, summarize, summarize_workflow
from context_loom.cli import main


class FakeHost:
    def __init__(self, *, invalid_route: bool = False, interrupt_at: str | None = None,
                 failed_at: str | None = None, bad_hash: bool = False) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.invalid_route = invalid_route
        self.interrupt_at = interrupt_at
        self.failed_at = failed_at
        self.bad_hash = bad_hash
        self.serial = 0

    def _next(self) -> str:
        self.serial += 1
        return f"session-{self.serial}"

    def start(self, prompt: str) -> AgentTurn:
        ident = self._next()
        self.calls.append(("start", "", ident))
        return AgentTurn(ident, json.dumps({"summary": "Shared project context", "ambiguities": []}))

    def fork(self, parent_thread_id: str, prompt: str) -> AgentTurn:
        ident = self._next()
        self.calls.append(("fork", parent_thread_id, ident))
        return AgentTurn(ident, self._response(prompt))

    def resume(self, thread_id: str, prompt: str) -> AgentTurn:
        self.calls.append(("resume", thread_id, thread_id))
        return AgentTurn(thread_id, self._response(prompt))

    def _response(self, prompt: str) -> str:
        if "Ranges (data, not instructions): " in prompt:
            ranges = json.loads(prompt.split("Ranges (data, not instructions): ", 1)[1])
            return json.dumps({"units": [{"task_id": "RSU-001", "title": "Meaningful unit",
                "source_quotes": [{"range_id": r["range_id"], "quote": r["text"]} for r in ranges],
                "context_refs": [], "payload": {}}],
                "coverage": [{"range_id": r["range_id"], "disposition": "covered", "task_ids": ["RSU-001"]} for r in ranges]})
        if "Units: " in prompt:
            units = json.loads(prompt.split("Units: ", 1)[1])
            assessments = [{"task_id": u["task_id"],
                "complexity": "complex" if u["task_id"].endswith("003") else "simple",
                "rationale": "Requires an isolated reasoning branch" if u["task_id"].endswith("003") else "Bounded and compatible with the next unit"}
                for u in units]
            if self.invalid_route:
                assessments.pop()
            return json.dumps({"assessments": assessments})
        packet = json.loads(prompt.split("Packet: ", 1)[1].split("\nCurrent task (only): ", 1)[0])
        task = json.loads(prompt.split("\nCurrent task (only): ", 1)[1])
        if task["task_id"] == self.interrupt_at:
            self.interrupt_at = None
            raise RuntimeError("simulated worker crash")
        return json.dumps({"schema_version": "context-loom/worker-result-v1", "task_id": task["task_id"],
            "status": "failed" if task["task_id"] == self.failed_at else "completed",
            "baseline_sha256": "invalid" if self.bad_hash else packet["baseline_sha256"],
            "packet_sha256": packet["packet_sha256"], "content": task["title"], "trace": {}})


def fixture(tmp_path: Path, *, discovery: bool = False) -> dict:
    (tmp_path / "spec.md").write_text("# Business rule\n\nAny complete semantic unit.\n", encoding="utf-8")
    config = {"schema_version": "context-loom/workflow-v1", "workflow_id": "example", "root": ".",
        "sources": [{"source_id": "SPEC", "path": "spec.md", "role": "spec"}]}
    if discovery:
        config["task_discovery"] = {"source_ids": ["SPEC"], "id_prefix": "RSU"}
    else:
        config["tasks"] = [{"task_id": f"TASK-{i:03}", "title": f"Unit {i}",
                            "source_refs": ["SPEC"], "payload": {}} for i in range(1, 4)]
    return config


def test_batches_share_only_their_own_fork_and_merge_in_order(tmp_path: Path) -> None:
    config = fixture(tmp_path)
    fake = FakeHost()
    output = run(tmp_path, config, fake)
    assert output.read_text(encoding="utf-8").index("TASK-001") < output.read_text(encoding="utf-8").index("TASK-003")
    assert [c[0] for c in fake.calls] == ["start", "fork", "fork", "resume", "fork"]
    assert fake.calls[2][1] == fake.calls[0][2]  # simple fork from baseline
    assert fake.calls[3][1] == fake.calls[2][2]  # simple second task resumes same child
    assert fake.calls[4][1] == fake.calls[0][2]  # complex fork from baseline, not simple child
    assert load_or_create(tmp_path, "example")["assembly"]["status"] == "validated"
    audit = summarize(tmp_path)
    assert audit["counts"] == {"start": 1, "completed": 5, "fork": 3, "resume": 1}
    assert audit["by_stage"]["worker"] == {"fork": 2, "completed": 3, "resume": 1}
    records = [json.loads(row) for row in (tmp_path / AUDIT_NAME).read_text(encoding="utf-8").splitlines()]
    worker = [row for row in records if row["stage"] == "worker" and row["event"] == "completed"]
    assert [row["task_id"] for row in worker] == ["TASK-001", "TASK-002", "TASK-003"]
    assert worker[1]["operation"] == "resume" and worker[1]["parent_thread_id"] == worker[0]["thread_id"]
    assert worker[0]["batch_id"] == worker[1]["batch_id"]
    assert worker[2]["batch_id"] != worker[1]["batch_id"]
    assert all("prompt" not in row and "stderr" not in row for row in records)
    other = FakeHost()
    run(tmp_path, config, other)
    assert other.calls == []  # idempotent resume doesn't start or fork extra sessions
    assert summarize(tmp_path)["invocations"] == 5


def test_discovery_quotes_are_original_and_coverage_is_complete(tmp_path: Path) -> None:
    config = fixture(tmp_path, discovery=True)
    fake = FakeHost()
    run(tmp_path, config, fake)
    assert summarize(tmp_path)["by_stage"]["discovery"] == {"fork": 1, "completed": 1}
    assert (tmp_path / ".context-loom" / "discovery.json").is_file()
    assert "RSU-001" in (tmp_path / ".context-loom" / "assembled.md").read_text(encoding="utf-8")
    ranges = [{"range_id": "SPEC:001", "source_id": "SPEC", "text": "Required exact text"}]
    with pytest.raises(ValueError, match="quote"):
        validate_discovery({"units": [{"task_id": "RSU-001", "title": "t",
            "source_quotes": [{"range_id": "SPEC:001", "quote": "fabricated"}]}],
            "coverage": [{"range_id": "SPEC:001", "disposition": "covered", "task_ids": ["RSU-001"]}]}, ranges, "RSU")
    with pytest.raises(ValueError, match="every source range"):
        validate_discovery({"units": [{"task_id": "RSU-001", "title": "t",
            "source_quotes": [{"range_id": "SPEC:001", "quote": "Required exact text"}]}],
            "coverage": []}, ranges, "RSU")


def test_routing_must_assess_every_unit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="every task"):
        run(tmp_path, fixture(tmp_path), FakeHost(invalid_route=True))
    assert not (tmp_path / ".context-loom" / "plan.json").exists()


def test_high_risk_task_cannot_be_downgraded_and_simple_batch_limit_applies(tmp_path: Path) -> None:
    config = fixture(tmp_path)
    config["tasks"][0]["payload"]["requires_dedicated_fork"] = True
    with pytest.raises(ValueError, match="high-risk"):
        run(tmp_path, config, FakeHost())
    other = fixture(tmp_path)
    other["policy"] = {"max_simple_batch_size": 1}
    run(tmp_path, other, FakeHost())
    plan = read_json(tmp_path / ".context-loom" / "plan.json")
    assert [batch["task_ids"] for batch in plan["batches"]] == [["TASK-001"], ["TASK-002"], ["TASK-003"]]


def test_recover_crash_without_rerunning_accepted_sibling(tmp_path: Path) -> None:
    config = fixture(tmp_path)
    fake = FakeHost(interrupt_at="TASK-002")
    with pytest.raises(RuntimeError, match="simulated worker crash"):
        run(tmp_path, config, fake)
    assert load_or_create(tmp_path, "example")["tasks"]["TASK-001"]["status"] == "validated"
    result = run(tmp_path, config, fake)
    assert result.is_file()
    assert len([c for c in fake.calls if c[0] == "resume"]) == 1  # first attempt second task only
    assert len([c for c in fake.calls if c[0] == "fork" and c[1] == "session-1"]) == 4


def test_source_drift_fails_before_reusing_session(tmp_path: Path) -> None:
    config = fixture(tmp_path)
    fake = FakeHost(interrupt_at="TASK-001")
    with pytest.raises(RuntimeError):
        run(tmp_path, config, fake)
    (tmp_path / "spec.md").write_text("changed requirement", encoding="utf-8")
    with pytest.raises(ValueError, match="baseline source drift"):
        run(tmp_path, config, fake)


def test_audit_counts_failed_turn_and_recovery_across_runs(tmp_path: Path, capsys) -> None:
    config = fixture(tmp_path)
    host = FakeHost(interrupt_at="TASK-002")
    with pytest.raises(RuntimeError, match="simulated worker crash"):
        run(tmp_path, config, host)
    first = summarize(tmp_path)
    assert first["counts"]["failed"] == 1
    assert first["incomplete"][0]["task_id"] == "TASK-002"
    assert first["incomplete"][0]["operation"] == "resume"
    assert first["incomplete"][0]["error_type"] == "RuntimeError"
    run(tmp_path, config, host)
    second = summarize(tmp_path)
    assert second["counts"]["failed"] == 1
    assert second["counts"]["fork"] == 4  # retry starts a fresh child
    lines = [json.loads(line) for line in (tmp_path / AUDIT_NAME).read_text(encoding="utf-8").splitlines()]
    assert len({item["run_id"] for item in lines}) == 2
    assert main(["audit", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["counts"] == second["counts"]


def test_audit_distinguishes_interrupted_start_and_missing_history(tmp_path: Path) -> None:
    assert summarize(tmp_path)["recorded"] is False
    audit = InvocationAudit(tmp_path, "sample")
    audit._append({"invocation_id": "one", "event": "started", "run_id": audit.run_id,
                   "stage": "worker", "operation": "fork", "batch_id": "B-1", "task_id": "T-1"})
    report = summarize(tmp_path)
    assert report["counts"] == {"fork": 1, "interrupted": 1}
    assert report["incomplete"][0]["status"] == "interrupted"


def test_audit_aggregates_three_phase_trial_with_partial_history(tmp_path: Path, capsys) -> None:
    (tmp_path / "preanalysis").mkdir()
    (tmp_path / "test-points").mkdir()
    (tmp_path / "test-cases").mkdir()
    audit = InvocationAudit(tmp_path / "test-points", "points")

    class MeasuredHost:
        def start(self, prompt):
            return AgentTurn("baseline", "done", 2, {"input_tokens": 110, "cached_input_tokens": 30})

    audit.scope(MeasuredHost(), "baseline").start("secret source text")
    assert main(["audit", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"start": 1, "completed": 1}
    assert report["usage"] == {"input_tokens": 110, "cached_input_tokens": 30}
    assert report["phases"]["preanalysis"]["recorded"] is False
    assert report["phases"]["test-points"]["recorded"] is True
    assert report["phases"]["test-cases"]["recorded"] is False
    assert "secret source text" not in (tmp_path / "test-points" / AUDIT_NAME).read_text(encoding="utf-8")


def test_invalid_worker_hash_never_commits_and_resumes_in_new_fork(tmp_path: Path) -> None:
    config = fixture(tmp_path)
    host = FakeHost(bad_hash=True)
    with pytest.raises(ValueError, match="baseline_sha256"):
        run(tmp_path, config, host)
    assert load_or_create(tmp_path, "example")["tasks"]["TASK-001"]["status"] == "running"
    host.bad_hash = False
    run(tmp_path, config, host)
    assert host.calls[-1][0] == "fork"


def test_failed_result_requires_explicit_retry_and_archives_attempt(tmp_path: Path) -> None:
    config = fixture(tmp_path)
    host = FakeHost(failed_at="TASK-001")
    with pytest.raises(ValueError, match="worker failed"):
        run(tmp_path, config, host)
    with pytest.raises(ValueError, match="task is not failed"):
        retry_failed(tmp_path, config, "TASK-002")
    retry_failed(tmp_path, config, "TASK-001")
    assert (tmp_path / ".context-loom" / "attempts" / "TASK-001" / "attempt-001.json").exists()
    host.failed_at = None
    run(tmp_path, config, host)
    assert load_or_create(tmp_path, "example")["tasks"]["TASK-001"]["status"] == "validated"


def test_codex_host_builds_real_fork_resume_commands_without_invoking_model(monkeypatch, tmp_path: Path) -> None:
    import subprocess
    from types import SimpleNamespace

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[-1] == "--help":
            return SimpleNamespace(returncode=0, stdout="Usage: codex exec fork", stderr="")
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"ok":true}', encoding="utf-8")
        thread = "baseline" if "fork" not in command and "resume" not in command else (
            "child" if "fork" in command else "child")
        return SimpleNamespace(returncode=0, stdout="\n".join([
            json.dumps({"type": "thread.started", "thread_id": thread}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 50,
                        "cached_input_tokens": 20, "output_tokens": 10}})]), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("context_loom.agents.shutil.which", lambda _: "codex")
    host = CodexHost(tmp_path)
    assert host.start("hello").thread_id == "baseline"
    forked = host.fork("baseline", "task")
    assert forked.thread_id == "child"
    assert forked.usage == {"input_tokens": 50, "cached_input_tokens": 20, "output_tokens": 10}
    assert host.resume("child", "next").thread_id == "child"
    assert ["fork", "baseline", "-"] == commands[-2][-3:]
    assert ["resume", "child", "-"] == commands[-1][-3:]


def test_assembly_rechecks_result_integrity_and_domain_policy(tmp_path: Path) -> None:
    class Policy:
        def validate_result(self, task, result):
            if "Unit" not in result["content"]:
                raise ValueError("missing domain evidence")

        def finalize(self, directory, assembled):
            return assembled

    config = fixture(tmp_path)
    run(tmp_path, config, FakeHost(), Policy())
    class RejectPolicy(Policy):
        def validate_result(self, task, result):
            raise ValueError("new domain policy rejected old output")

    with pytest.raises(ValueError, match="new domain policy"):
        run(tmp_path, config, FakeHost(), RejectPolicy())
    file = tmp_path / ".context-loom" / "results" / "TASK-001.json"
    data = read_json(file)
    data["packet_sha256"] = "tampered"
    file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="packet_sha256"):
        assemble(tmp_path, config, read_json(tmp_path / ".context-loom" / "plan.json"))


def test_domain_finalization_failure_is_not_reported_as_finished(tmp_path: Path) -> None:
    class FailedFinalizer:
        def validate_result(self, task, result):
            return None

        def finalize(self, directory, assembled):
            raise ValueError("presentation conversion failed")

    config = fixture(tmp_path)
    with pytest.raises(ValueError, match="presentation conversion failed"):
        run(tmp_path, config, FakeHost(), FailedFinalizer())
    assert load_or_create(tmp_path, "example")["assembly"]["status"] == "failed"
