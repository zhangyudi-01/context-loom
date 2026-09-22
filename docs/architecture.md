# Architecture

Context Loom has three layers:

```text
skills/                  user-facing domain workflows
src/context_loom/        model-independent deterministic runtime
schemas/                 portable contracts for adapters and workers
```

The runtime is deliberately split by responsibility:

- `baseline`: resolve authoritative sources and compile a fingerprinted shared context;
- `planning`: classify Task Units and create compatible batches or dedicated forks;
- `execution`: create bounded packets and accept structured results;
- `state`: persist recovery state atomically;
- `validation`: reject scope, hash, status, or schema drift;
- `assembly`: order and render only accepted results.

The framework does not decide what a test point, design task, or research finding means. A
domain workflow supplies that meaning through its task payload and result contract.

