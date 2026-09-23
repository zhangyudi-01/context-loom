# Testing RSU discovery example

This configuration illustrates the boundary between generic task discovery and the software-
testing domain. `GLOBAL` and `MODULE` are authoritative baseline sources; only the module is
partitioned into auditable coverage ranges. The model proposes semantic RSUs backed by literal
quotes; the number of Markdown headings does not determine the number of RSUs. The optional
`DATA-CLOSURE` file is a dynamic context only for units that explicitly reference it.

From the repository root, `context-loom run examples/testing-rsu-discovery` performs **real AI
calls** and costs model tokens. This is a toy example, not the production testing runner and
not a substitute for domain-specific coverage and result review.
