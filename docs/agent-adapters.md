# Agent adapters

The `AgentHost` interface (`start`, `fork`, `resume`) separates generic orchestration from vendor
sessions. `CodexHost` is an implemented read-only CLI adapter: `context-loom run WORKFLOW_DIR`
creates one baseline session; discovery and routing fork from it; each batch independently forks
from the baseline. Simple members then use `resume` on that batch's child. No sibling batch
inherits another batch's history. An adapter must return a real child session ID on `fork` and
must preserve the same ID on `resume`. The parent validates each result and persists a JSON ledger.
Agent conversation logs are never used to schedule or resume work. Other hosts can implement the
same interface; Claude integration is not implemented yet. Automatic compaction is not required.
