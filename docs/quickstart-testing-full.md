# Try the complete software-testing flow in isolation

The `loom-testing-full` Skill guides a fresh, read-only-source trial on a preanalyzed module.
Install Skills and the Python runtime separately; running the model is a paid operation.

```powershell
npx skills@latest add zhangyudi-01/context-loom --skill loom-testing-full --agent codex --global --yes
python -m pip install "git+https://github.com/zhangyudi-01/context-loom.git"
```

In Codex, invoke `$loom-testing-full` with an existing module directory and an **unused**
output directory outside its source project. Alternatively, run:

```powershell
context-loom setup-testing-full --module <absolute-module-dir> --output <new-trial-directory>
context-loom run-testing-full <new-trial-directory> --timeout 900
```

`setup-testing-full` snapshots required sources and records their hashes. The original
module's requirement, confirmed context, clarifications and context/data cards are read-only
inputs. The run makes fresh AI calls to discover source-quoted RSUs (it does not copy the
existing RSU map), verifies coverage of the task-list module's eight numbered business rules,
generates test points for **all** discovered RSUs, and generates cases for **all** accepted
test points. Results and JSON checkpoints remain under the new trial directory:

```text
<trial>/preanalysis/                   RSU discovery and generated mapping
<trial>/test-points/.context-loom/     per-RSU results and module-test-points.md
<trial>/test-cases/.context-loom/      per-TP results and module-test-cases.md
<trial>/test-cases/sql/                optional shared read-only query template
<trial>/completion.json               counts and SHA-256 output digests
<trial>/quality-review.json            heuristic quality findings for human review
<trial>/test-cases/review-adjustments.json  optional hash-bound reviewer amendments
```

Re-run the **same** `run-testing-full` command after a recoverable interruption: JSON state
and input hashes determine what is reused. Do not start two runners on the same directory.
Any result marked `pipeline-complete` still needs a semantic review of requirement coverage,
case duplication, executable steps, SQL relevance and boundaries. The optional SQL is a static
comparison template, **not** an executed or database-verified query. This task-list trial
has domain-specific discovery guidance and is not a universal replacement for the source
project's three production Skills. Do not commit trial data or local absolute paths publicly.

When a generated case needs an editorial correction, a `review-adjustments.json` entry keyed
by TP-ID may supply `source_sha256` (the SHA-256 of the raw `results/TP-xxx.json`), a `reason`,
and the corrected `title`, `prerequisite`, `steps` and `expected`. The original model result
remains intact for audit; re-running applies the correction without another model call.
The run rejects stale hashes and records the adjustment count in `completion.json`.
