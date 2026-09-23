---
name: testing-requirement-preanalysis
description: Compile a software-testing module's requirements, global context, source mappings, questions, and data closures into a traceable input for test-point generation. Use only for testing-domain requirement preanalysis.
---

# Testing requirement preanalysis adapter

This adapter supplies testing-domain semantics to Context Loom. Preserve requirement wording,
map semantically complete RSUs, record clarification and data-closure references, and emit a
domain packet that the generic workflow runtime can route and validate. Configure
`task_discovery.source_ids` for requirement sources and `task_discovery.id_prefix: "RSU"`; source
range IDs are coverage checkpoints, **not** a command to split by heading or sentence. Require
literal citations, whole semantic contracts, exclusions with reasons, and domain review of
ambiguous requirements. Put global knowledge and module requirements in `sources`, dynamic
data closures in `contexts` and unit `context_refs`. It does not define the generic baseline,
state machine, fork lifecycle, or deterministic assembly. This is an adapter specification,
not a claim that the project-local preanalysis runner has been migrated.
