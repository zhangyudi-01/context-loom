"""Replaceable domain policy; task semantics never belong in the generic scheduler."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class DomainAdapter(Protocol):
    def validate_result(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        """Raise ValueError on unmet domain-specific quality, provenance, or content rules."""

    def finalize(self, workflow_dir: Path, assembled_markdown: Path) -> Path:
        """Optionally convert validated results to a domain deliverable (e.g. PPTX)."""


class MarkdownAdapter:
    """Default generic adapter: only the core schema and source hashes are enforced."""

    def validate_result(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        return None

    def finalize(self, workflow_dir: Path, assembled_markdown: Path) -> Path:
        return assembled_markdown
