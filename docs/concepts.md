# Core concepts

## Understand once

Compile authoritative sources into a Baseline. The Baseline is a cache with fingerprints, not a
replacement for the sources.

## Fork with memory

Every packet references the same Baseline but contains only the assigned tasks. A dedicated fork
inherits shared understanding without inheriting sibling worker conversation or tool history.

## Focus on one task

Simple compatible tasks may share a batch; complex tasks receive a dedicated fork. The task
payload is the domain's responsibility.

## Verify and merge

Results must match the active Baseline and packet hashes. The assembler emits only validated
results in deterministic task order.

