# Context Loom

## Skills for Focused, High-Quality AI Work

让 AI 不迷失上下文，聚焦当前任务，持续产出高质量成果。

A reusable AI workflow framework for shared-context reasoning, complexity-aware forking, focused execution, and traceable aggregation.

> Understand once.  
> Fork with memory.  
> Focus on one task.  
> Verify and merge.

![Context Loom skill card: skills for focused, high-quality AI work](docs/assets/context-loom-skill-card.svg)

Context Loom turns long, context-heavy AI work into bounded, verifiable units without making
every worker rediscover the project from scratch. It compiles shared sources into a fingerprinted
baseline, routes work by complexity, prepares focused worker packets, validates structured
results, and assembles accepted results deterministically.

It is not one giant prompt and it is not tied to a single model. The framework separates:

- **Skills** — user-facing workflows organized by engineering domain.
- **Runtime** — deterministic baseline, planning, state, validation, and assembly code.
- **Adapters** — integrations that map the execution plan to Codex, Claude, or another agent host.

## The workflow

![Context Loom core workflow: shared sources, fingerprinted baseline, complexity routing, focused execution plans, validation, and assembly](docs/assets/context-loom-core-workflow.svg)

Two modes are available: a manual control plane (`compile → plan → prepare-next → submit → assemble`)
and `run`, which creates a real shared Codex session, discovers source-backed task units when
configured, asks AI to evaluate **every** unit's complexity, then forks independent batches.
Simple units in the same batch run sequentially in one child session; complex units fork alone.
The parent validates each result before committing it and assembles in declared order. This
agent-driven mode uses model tokens; tests use a fake host and incur no model charges.

## Repository layout

```text
skills/                         User-facing, composable workflows
  framework/                    Context Loom setup and orchestration
  engineering/software-testing First domain workflow
src/context_loom/               Reusable deterministic runtime
schemas/                        Portable JSON contracts
docs/                           Architecture and extension guides
examples/                       Runnable workflow examples
tests/                          Runtime and end-to-end verification
```

## Quick start

### Install the Skills

In your own interactive terminal, install the workflow Skills with the same `skills` installer
used by other Skills repositories:

```powershell
npx skills@latest add zhangyudi-01/context-loom
```

The installer discovers the Skills in this repository and, when running interactively,
lets you select which Skills and agent integrations to install. For example, choose
`loom-test-points` for an isolated test-point pilot; `context-loom` and
`setup-context-loom` are the framework entry points. The menu and its visual style belong
to the external `skills` installer, not to this repository. Agent-hosted or CI terminals
may be treated as non-interactive and install all discovered Skills instead. To select
exactly one Skill without a menu, use:

```powershell
npx skills@latest add zhangyudi-01/context-loom --skill loom-test-points --agent codex --global --yes
```

Installing Skills provides agent instructions **only**; it does not install the Python
`context-loom` runtime. Install the runtime separately before using its commands:

```powershell
python -m pip install "git+https://github.com/zhangyudi-01/context-loom.git"
context-loom --help
```

If you are developing the framework locally, use the editable checkout below instead.

### Run the framework locally

```powershell
git clone https://github.com/zhangyudi-01/context-loom.git
cd context-loom
python -m pip install -e .

context-loom init .\demo --workflow-id demo-workflow
context-loom compile .\demo
context-loom plan .\demo
context-loom prepare-next .\demo
```

An agent adapter consumes the packet and returns one structured result per task:

```powershell
context-loom submit .\demo --result .\worker-result.json
context-loom assemble .\demo
context-loom status .\demo
```

For an automated run (requires a compatible Codex CLI and may incur model costs):

```powershell
context-loom run .\demo
context-loom status .\demo
```

To derive task units instead of listing them manually, set `task_discovery` with `source_ids`
and `id_prefix` in the workflow configuration; discovery requires source quotations and complete
range coverage. On failure, inspect `status`, then explicitly requeue with
`context-loom retry-failed .\demo --task-id TASK-001` before rerunning. Input files and routing
cannot drift during recovery. See [agent adapters](docs/agent-adapters.md) and
[the lifecycle](docs/workflow-lifecycle.md) for boundaries.

See [the minimal example](examples/minimal-workflow/README.md) for a complete local run.

For a read-only trial on an existing software-testing module, see the
[isolated testing pilot](docs/quickstart-testing-pilot.md). `$loom-test-points` guides setup,
preflight and the optional paid run; it does not overwrite the original module's artifacts.

## Core invariants

1. **Source files remain the facts.** A baseline is a compiled, fingerprinted view, not a replacement.
2. **Every task is bounded.** A worker receives the shared baseline plus only its authorized task scope.
3. **Complexity changes topology.** Compatible simple tasks share a child session; complex tasks receive their own fork.
4. **Sibling history is not evidence.** One task cannot depend on another worker's conversation or tool trace unless declared.
5. **State is explicit.** JSON state and file hashes control recovery; logs are audit evidence, not scheduling input.
6. **AI reasons locally; code assembles globally.** Accepted results are ordered and merged deterministically.

## Current status

The generic control plane and initial Codex CLI host implement:

- baseline source resolution and SHA-256 fingerprints;
- optional source-faithful AI discovery and exhaustive AI complexity routing;
- real shared-baseline sessions and sibling-isolated Codex forks with bounded simple batches;
- atomic workflow state;
- focused packet generation;
- structured result submission and scope validation;
- deterministic Markdown assembly and traceability JSON;
- initial Context Loom and software-testing Skill guidance (not a full migration of the original project's runners);
- programmatic domain validation and artifact-finalization hooks;
- portable JSON schemas and a runnable example.

Claude and presentation-specific adapters, concurrent batch execution, and a full production
migration of the original testing Skills are **not** implemented. The Codex adapter is read-only;
the runtime runs batches sequentially by default and does not depend on automatic compaction.

## Documentation

- [Architecture](docs/architecture.md)
- [Core concepts](docs/concepts.md)
- [Workflow lifecycle](docs/workflow-lifecycle.md)
- [Writing a domain workflow](docs/writing-a-domain-workflow.md)
- [Agent adapters](docs/agent-adapters.md)
- [Migration from existing testing Skills](docs/migration-from-existing-skills.md)

## License

MIT
