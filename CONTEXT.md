# Context Loom Glossary

## Baseline

A compiled and fingerprinted shared-context packet. It gives workers common understanding
without making worker conversation history a source of truth.

## Source

An authoritative project file registered by a workflow. Sources remain the facts even after
a Baseline is compiled.

## Task Unit

The smallest independently authorized work item. A Task Unit has a stable ID, explicit source
and context references, a complexity classification, and a domain payload.

## Batch

An execution group containing compatible simple Task Units. A Batch shares a baseline and
context signature, but every contained Task Unit still produces an independently traceable result.

## Dedicated Fork

An execution group containing exactly one complex Task Unit. It inherits the Baseline but does
not inherit sibling worker history.

## Worker Packet

The bounded, self-contained input prepared for one Batch or Dedicated Fork.

## Worker Result

A structured result for one Task Unit. It records the Task Unit ID, baseline and packet hashes,
status, content, and traceability metadata.

## Assembly

The deterministic ordering and rendering of validated Worker Results into the final artifact.

## Domain Workflow

A set of Skills, policies, schemas, and optional renderers that defines what Task Units mean in
a specific engineering discipline. Software testing is the first Domain Workflow.

