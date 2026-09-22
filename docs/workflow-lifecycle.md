# Workflow lifecycle

```text
init → compile → plan → prepare-next → submit (repeat) → assemble
```

The state file is `.context-loom/state.json`. It is the sole scheduler and recovery source.
Packets and results are immutable evidence for their stage. A failed task or batch is visible in
state and must be repaired or retried before assembly.

