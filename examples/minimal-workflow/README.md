# Minimal workflow

This example demonstrates the full Context Loom control plane without coupling the runtime to
Codex, Claude, or another agent host. The committed `context-loom.json` declares two source
files and three tasks: two simple tasks and one complex task. The complex task is routed to a
dedicated fork, while compatible simple tasks may share a batch.

Run it from the repository root:

```powershell
python -m context_loom.cli compile examples/minimal-workflow
python -m context_loom.cli plan examples/minimal-workflow
python -m context_loom.cli prepare-next examples/minimal-workflow
```

`prepare-next` writes a bounded packet under `.context-loom/packets/`. An adapter should invoke
its worker with that packet and create one result JSON per task. Copy the active packet's
`baseline_sha256` and `packet_sha256` into [worker-result.template.json](worker-result.template.json),
set the task ID and content, then submit it:

```powershell
python -m context_loom.cli submit examples/minimal-workflow --result .\worker-result.json
```

Repeat `prepare-next` and `submit` until it prints `NO_PENDING_BATCH`, then assemble:

```powershell
python -m context_loom.cli assemble examples/minimal-workflow
python -m context_loom.cli status examples/minimal-workflow
```

The final Markdown and traceability data are generated under `.context-loom/`. That directory is
runtime state and is ignored by Git; the committed files are the reusable fixture and its source
context.
