---
name: setup-context-loom
description: Configure a repository to use Context Loom by identifying its authoritative sources, workflow directory, and domain adapter. Use once when introducing Context Loom to a project.
---

# Setup Context Loom

Inspect the repository before writing configuration. Identify the project root, authoritative
context files, and the domain workflow that will supply task semantics. Create a small
`context-loom.json` with explicit source paths and task units. Never copy a project's knowledge
base into the Context Loom repository; register it as an external workflow source instead.
