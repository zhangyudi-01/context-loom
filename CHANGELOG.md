# Changelog

## Unreleased

- Complete the conversational `testing-requirement-preanalysis` Skill with self-contained
  domain contracts, templates, scaffolding, semantic-structure/source validation and tests.
  Keep original requirements read-only; write new analyses under `preanalysis/` without
  starting paid model sessions or generating downstream artifacts.
- Support `preanalysis/v1` manifests in testing pilot setup, including remapped resource roles,
  scoped dependencies and supporting RSU rows. Reject unresolved/blocked selected inputs,
  ambiguous manifests and out-of-bounds paths before creating a pilot directory.
- Add a local preanalysis quick start and distinguish the full conversational Skill from
  the remaining trial/design adapters.

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
