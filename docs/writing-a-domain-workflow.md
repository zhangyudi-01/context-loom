# Writing a domain workflow

A domain workflow should define:

1. What its Task Unit means.
2. What sources and context are authoritative.
3. How complexity is judged.
4. The result schema and validation rules.
5. The final artifact and traceability fields.

It should not reimplement source fingerprinting, atomic state, generic packet routing, or result
assembly. Add a Skill under `skills/engineering/<domain>/`, a domain payload contract, and an
adapter test that exercises the generic lifecycle. Register a Python `DomainAdapter` when the
generic worker-result schema is not enough: `validate_result(task, result)` checks meaning before
commit and `finalize(workflow_dir, assembled_markdown)` creates a domain deliverable, such as a
presentation, from validated results. The default is `MarkdownAdapter`. Supply the adapter to
`context_loom.orchestrator.run(workflow_dir, config, host, adapter)`; the CLI uses the generic
Markdown adapter. A presentation adapter must handle its own slide/binary artifact validation;
the core does not claim to create PPTX files.
