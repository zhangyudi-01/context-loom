---
name: context-loom
description: Run a bounded AI workflow with a shared fingerprinted baseline, complexity-aware batching or dedicated forks, structured result validation, and deterministic assembly. Use when a project has context-heavy work that must remain focused and traceable.
---

# Context Loom

Use the Context Loom runtime as the control plane for a multi-task AI workflow.

1. Register authoritative sources and either explicit tasks or `task_discovery` in `context-loom.json`.
2. Use `context-loom run WORKFLOW_DIR` for agent-driven orchestration, or the manual CLI commands for a controlled workflow. Agent-driven runs use model tokens and require a Codex CLI with `exec fork` support.
3. Compile the source-fingerprinted Baseline and create one shared understanding session. Discover semantic units when configured, checking literal evidence and source coverage.
4. From the baseline, route every unit by AI-assessed complexity. Batch only compatible simple units; give each complex unit an isolated fork.
5. In each simple batch fork, execute units sequentially in the same child session; validate and record each result before proceeding. Parent state, not session logs, drives recovery.
6. Assemble validated results in declared task order. Fail closed on missing coverage, source drift, or invalid worker output.

The runtime owns state, hashes, routing, validation, and assembly. A domain Skill owns the
meaning of a task and the shape of its content. Do not put domain-specific assumptions in
the core workflow configuration.

Use the CLI described in the repository README. Logs are audit evidence; `.context-loom/state.json`
is the recovery source. A worker must not use sibling worker history as business evidence.
