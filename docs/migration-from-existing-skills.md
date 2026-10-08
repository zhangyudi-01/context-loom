# Migration from existing testing Skills

Keep the existing project-local `.codex/skills/` production workflows unchanged. Migrate by
implementing an adapter that translates their module baseline, RSU/TP task units, and result
artifacts into Context Loom packets. Run both paths on a fixture before replacing any project
runner. The first migration target is the testing domain; no project knowledge base is copied
into this repository.

Mapping: module preanalysis supplies source-quoted RSUs and range-coverage decisions; the
test-point runner consumes validated RSUs as focused tasks; the test-case runner consumes
validated TPs with scoped SQL/data-closure context. Each stage is a separate workflow with its
own source fingerprint and domain checks. The generic runtime provides baseline reuse, exhaustive
routing and isolated execution, **not** automatic correctness of RSU, TP, TC, or SQL content.
The requirement-preanalysis Skill is now a complete conversational workflow: it includes
domain references, templates, scaffolding and the original source/coverage/parent-behavior/
Q/FC/DC validator. It writes new analysis under the module's `preanalysis/` directory and
does not need the Context Loom runtime or an independent AI runner. Original materials and
project-local Skills remain unchanged. See [its quick start](quickstart-testing-preanalysis.md).

`setup-testing` now consumes its `preanalysis/v1` manifest, resolves remapped fixed resource
roles, and gives each selected task its complete RSU row plus direct Q/FC/DC/source dependencies
and any supporting RSU rows. Pending units, unresolved questions, blocked data closures and
ambiguous manifests are rejected before an output directory is created. This preparation is
not a substitute for running the producer's full validator.

The remaining testing Skills are design adapters or isolated trial workflows. They do not yet
reproduce the full production test-point/test-case validation, module-level convergence,
migrations or SQL collation logic. The earlier `loom-testing-full` snapshot trial is a separate
demonstration, not the preferred entry point for the original global/modules layout.
