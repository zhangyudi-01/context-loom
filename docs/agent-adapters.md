# Agent adapters

The core runtime does not invoke Codex, Claude, or another agent process. An adapter reads the
next packet, invokes the host, and writes one structured result per Task Unit. It must preserve
`baseline_sha256`, `packet_sha256`, and `task_id` exactly. Agent conversation logs are optional
audit evidence and never replace workflow state.

