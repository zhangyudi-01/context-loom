---
name: loom-test-points
description: Run an isolated, source-quoted Context Loom test-point pilot for selected RSUs in an already-preanalyzed software-testing module. Use when the user asks to try Context Loom on an existing module without changing its original artifacts.
---

# Loom test points

Use the existing module as read-only input. This is a **pilot**, not a replacement for the
project's production test-point runner. Do not write into the source project or claim full
module coverage from a selected subset of RSUs.

1. Locate the module's `00-module-requirement-pack.md`, `01-context-pack.md`, and
   `02-sentence-test-point-map.md`. Choose the RSU IDs requested by the user; when none are
   specified, suggest one or two small, representative RSUs for a low-cost first run.
2. Create a **new** output directory outside the source project with
   `context-loom setup-testing --module MODULE_DIR --output NEW_DIR --rsu RSU-001 RSU-002`.
   The command fails rather than overwriting an existing directory. It references the project's
   real sources and copies no private materials into the framework repository.
3. Run `context-loom doctor NEW_DIR` to check files and Codex CLI fork support without model
   calls. If the CLI is unavailable, `--offline` still checks inputs. `context-loom compile NEW_DIR`
   produces a no-cost baseline. Do not describe these checks as a successful AI generation run.
4. `context-loom run NEW_DIR` makes paid model calls. Tell the user its selected scope and cost
   implication before running if they have not already authorized paid validation. Review the
   generated `.context-loom/module-test-points.md` and `.context-loom/trace.json` after execution.
5. Never silently replace the original module's `test-points/module-test-points.md`. Human review
   and the production domain validator remain necessary before promoting pilot results.

If the Python runtime is not available, install the Context Loom Python package separately;
installing a Skill alone does not deploy it. The source-quoted result validator checks shape,
origin and duplicate titles within one RSU, not complete semantic coverage of a whole module.
