# Changelog

## Unreleased

- Audit every agent start/fork/resume attempt with append-only stage/task/session records,
  elapsed time, outcomes, tool calls and available Codex token usage. Summarize individual
  workflows or all three full-testing phases with `context-loom audit` without using logs
  as the recovery source.

## 0.1.0 - 2026-09-22

- Introduced the Context Loom control-plane package and CLI.
- Added fingerprinted baseline compilation and task packet generation.
- Added complexity-aware batch and dedicated-fork planning.
- Added atomic workflow state, structured result validation, and deterministic assembly.
- Added initial framework and software-testing Skills.
- Added JSON schemas, architecture documentation, examples, and tests.
