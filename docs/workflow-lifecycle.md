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
