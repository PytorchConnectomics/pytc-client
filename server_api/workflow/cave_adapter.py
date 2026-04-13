"""CAVE workflow adapter spike.

This module intentionally provides interface stubs only.
It is inert unless explicitly imported and called by future integration code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowArtifact:
    """App-level artifact payload expected by the adapter."""

    workflow_id: str
    artifact_uri: str
    dataset_id: str
    segmentation_id: str | None = None
    point_xyz: tuple[float, float, float] | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CavePayload:
    """Normalized payload to be consumed by a future CAVE client."""

    workflow_id: str
    datastack: str
    segmentation_ref: str | None
    point_xyz: tuple[float, float, float] | None
    provenance: dict[str, Any]


@dataclass(frozen=True)
class CaveResult:
    """Mapped adapter output normalized for app-level callers."""

    workflow_id: str
    cave_object_id: str
    status: str
    detail: dict[str, Any]


class CaveWorkflowAdapter:
    """Adapter interface scaffold for future CAVE integration.

    No network/auth behavior is implemented in this spike.
    """

    def build_payload(self, artifact: WorkflowArtifact) -> CavePayload:
        """Convert a workflow artifact into a CAVE payload.

        TODO: finalize mapping with production CAVE schema.
        """
        raise NotImplementedError("Spike scaffold: mapping logic is not implemented")

    def parse_result(self, workflow_id: str, response: dict[str, Any]) -> CaveResult:
        """Convert a CAVE response into a normalized app-level result.

        TODO: finalize result normalization once CAVE response schema is fixed.
        """
        raise NotImplementedError("Spike scaffold: result parsing is not implemented")
