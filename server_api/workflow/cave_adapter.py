"""CAVE integration scaffold for future workflow interoperability.

This module is intentionally inert unless explicitly instantiated and called by a
future integration path. It introduces data contracts and stub interfaces only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowArtifact:
    """Represents a workflow output produced by this app."""

    artifact_id: str
    artifact_type: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CavePayload:
    """Represents a CAVE-compatible payload shape."""

    table_name: str
    records: list[dict[str, Any]]
    provenance: dict[str, Any] = field(default_factory=dict)


class CaveAdapter:
    """Adapter stub for converting app workflow artifacts into CAVE payloads.

    This class does not perform network calls, authentication, or runtime side
    effects. It only defines an interface for future implementation.
    """

    def to_cave_payload(self, artifact: WorkflowArtifact) -> CavePayload:
        """Convert a workflow artifact to a CAVE payload.

        TODO: Implement artifact-type specific mappings.
        TODO: Validate payload schema against target CAVE tables.
        """
        raise NotImplementedError("Spike scaffold only; mapping not implemented.")

    def publish(self, payload: CavePayload) -> dict[str, Any]:
        """Publish a payload to a CAVE endpoint.

        TODO: Add authentication strategy assumptions (token/source/refresh flow).
        TODO: Add network transport and retry policy assumptions.
        TODO: Add deployment/runtime configuration assumptions.
        """
        raise NotImplementedError("Spike scaffold only; publishing not implemented.")
