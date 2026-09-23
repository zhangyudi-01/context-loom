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
The included testing Skills are design adapters. They do not yet implement the full project's
existing domain validation, migrations or SQL collation logic.
