# Workflow lifecycle

```text
manual: init → compile → plan → prepare-next → submit (repeat) → assemble
agent:  run → baseline session → optional discovery → exhaustive AI routing
            → (baseline fork per batch → result validation) (repeat) → assemble
```

The state file is `.context-loom/state.json`. It is the sole scheduler and recovery source.
The agent-mode baseline loads authoritative sources once per workflow, with a fingerprinted
session ID in `session.json`. Discovery and routing fork from that session independently.
Each simple batch forks once and resumes its own session for subsequent members; a complex unit
receives a dedicated fork. The default maximum simple batch size is 5 (`policy.max_simple_batch_size`,
valid 1–20). Session and source drift stop recovery; restarting the runner does not rescan logs or
automatically compress conversations. Packets and results are stage evidence. If interrupted
mid-batch, accepted tasks stay accepted, and remaining tasks restart in a new baseline fork.
For a failed result, call `retry-failed --task-id ID` explicitly: the failed attempt is archived
under `.context-loom/attempts/` before a fresh result can replace it.

Each attempted agent turn is also appended to `.context-loom/invocations.jsonl` as a
`started` event followed by `completed` or `failed`. The run ID ties attempts in the same
runner invocation together; stage, operation (`start`, `fork`, `resume`), parent and returned
session IDs, batch/task IDs, duration and tool-call count help explain actual execution.
If the Codex CLI emits turn usage, the completed record also contains input, cached-input,
and output token counts; unavailable usage is left `null` rather than estimated. These are
token counts, not prices or a guarantee of billable cost.
An unfinished `started` event indicates a possible process interruption, not a confirmed
successful CLI call. `context-loom audit WORKFLOW_DIR` summarizes recorded attempts and
failures; full JSONL is available for chronological inspection. This diagnostic audit is
never scanned for recovery, contains no prompts, source text or raw CLI stderr, and cannot
retroactively count calls made before this feature was enabled. Successful CLI calls whose
model output later fails validation remain `completed` here; consult `state.json` for the
validation/commit status. The Codex capability probe (`exec fork --help`) is not a model
turn and is not counted.
For the three-stage `run-testing-full` trial, invoke `context-loom audit TRIAL_ROOT` to
aggregate its `preanalysis`, `test-points`, and `test-cases` audit files. You may also
point it at one stage for its individual history.
