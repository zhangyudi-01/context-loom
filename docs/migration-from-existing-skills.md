# Migration from existing testing Skills

Keep the existing project-local `.codex/skills/` production workflows unchanged. Migrate by
implementing an adapter that translates their module baseline, RSU/TP task units, and result
artifacts into Context Loom packets. Run both paths on a fixture before replacing any project
runner. The first migration target is the testing domain; no project knowledge base is copied
into this repository.

