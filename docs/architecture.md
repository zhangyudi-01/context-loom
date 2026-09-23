# Architecture

Context Loom has three layers:

```text
skills/                  user-facing domain workflows
src/context_loom/        model-independent deterministic runtime
schemas/                 portable contracts for adapters and workers
```

The runtime is deliberately split by responsibility:

- `baseline`: resolve authoritative sources and compile a fingerprinted shared context;
- `discovery`: propose bounded semantic Task Units from quoted sources with coverage accounting;
- `orchestrator`: build one agent baseline, AI-route every unit, fork batches and resume simple members;
- `planning`: group AI-classified compatible tasks and isolate complex tasks;
- `execution`: create bounded packets and accept structured results;
- `state`: persist recovery state atomically;
- `validation`: reject scope, hash, status, or schema drift;
- `assembly`: order and render only accepted results.
- `domain`: optional programmatic domain-specific result validation and deliverable conversion.

The framework does not decide what a test point, design task, or research finding means. A
domain workflow supplies that meaning through its task payload and result contract.
The supplied CLI host is Codex; `AgentHost` is a protocol, not a Codex-specific core contract.
Sibling batches are isolated but currently execute **sequentially**; concurrency is not shipped.
