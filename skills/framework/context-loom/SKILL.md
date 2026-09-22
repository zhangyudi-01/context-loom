---
name: context-loom
description: Run a bounded AI workflow with a shared fingerprinted baseline, complexity-aware batching or dedicated forks, structured result validation, and deterministic assembly. Use when a project has context-heavy work that must remain focused and traceable.
---

# Context Loom

Use the Context Loom runtime as the control plane for a multi-task AI workflow.

1. Register authoritative sources and task units in `context-loom.json`.
2. Compile the Baseline once. Treat source files and their fingerprints as facts.
3. Plan simple compatible batches and dedicated forks for complex tasks.
4. Prepare one bounded Worker Packet at a time.
5. Submit structured results with the active Baseline and packet hashes.
6. Assemble only validated results, in declared task order.

The runtime owns state, hashes, routing, validation, and assembly. A domain Skill owns the
meaning of a task and the shape of its content. Do not put domain-specific assumptions in
the core workflow configuration.

Use the CLI described in the repository README. Logs are audit evidence; `.context-loom/state.json`
is the recovery source. A worker must not use sibling worker history as business evidence.

