---
name: testing-requirement-preanalysis
description: Compile a software-testing module's requirements, global context, source mappings, questions, and data closures into a traceable input for test-point generation. Use only for testing-domain requirement preanalysis.
---

# Testing requirement preanalysis adapter

This adapter supplies testing-domain semantics to Context Loom. Preserve requirement wording,
map semantically complete RSUs, record clarification and data-closure references, and emit a
domain packet that the generic workflow runtime can route and validate. It does not define the
generic baseline, state machine, fork lifecycle, or deterministic assembly.

