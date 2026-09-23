---
name: loom-testing-full
description: Run a fresh, isolated Context Loom end-to-end software-testing trial on an already-preanalyzed task-list module, from RSU discovery through all test points to all test cases, without changing the source module.
---

# Full-flow testing trial

Use only when the user requests an end-to-end testing trial; for a selected-RSU test-point
pilot, use `$loom-test-points`. Keep the source module read-only and choose a new output
directory outside its project. This entrypoint currently targets the task-list module's
eight numbered business rules, not arbitrary module structures.

1. Check the module has its requirement pack, confirmed context, RSU reference map,
   clarifications and relevant cards. Never treat old test points/cases as freshly generated.
2. Run `context-loom setup-testing-full --module MODULE --output NEW_DIR`, then
   `context-loom run-testing-full NEW_DIR --timeout 900`. AI execution incurs model costs;
   obtain authorization if the request did not already include it. The runner uses source
   hashes and JSON state for recovery: rerun the same command after an interruption, not a
   second simultaneous runner.
3. Review the generated RSU map, all test points, all test cases and `completion.json`.
   Check coverage, duplicates, executable steps, unnecessary SQL and source boundaries.
   Do not claim production equivalence merely because the pipeline completed. Never
   promote output into the source project without an explicit request.

For command details, outputs, limits and the optional SQL template, see
[full-flow quickstart](../../../../docs/quickstart-testing-full.md).
