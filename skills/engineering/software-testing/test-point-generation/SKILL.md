---
name: testing-test-point-generation
description: Generate traceable software-testing test points from validated requirement units using Context Loom baseline, complexity routing, focused workers, and deterministic assembly.
---

# Testing test-point generation adapter

Use the Context Loom runtime for planning and execution topology. Keep RSU, test-point,
coverage, source-candidate, and readiness semantics in this adapter. A test point must express
one independently executable and independently judgeable testing intent; do not create or merge
points to hit a target count. Use validated RSU artifacts as source-backed task units; list any
dynamic evidence by `context_refs`. Require the domain adapter to validate TP provenance and
semantic coverage before committing results. A simple RSU can share a sequential child session
with compatible peers; multi-branch or ambiguous RSUs require a dedicated fork. The production
project-local runner remains separate until a fixture-level migration test passes.
