"""Contract tests for CAVE adapter spike scaffolding."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path("server_api/workflow/cave_adapter.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("cave_adapter", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_adapter_module_can_be_loaded_explicitly_without_side_effects():
    module = _load_module()
    assert hasattr(module, "CaveWorkflowAdapter")
    assert hasattr(module, "WorkflowArtifact")


def test_adapter_interface_methods_are_stubbed_only():
    module = _load_module()
    adapter = module.CaveWorkflowAdapter()
    artifact = module.WorkflowArtifact(
        workflow_id="wf-1",
        artifact_uri="s3://bucket/artifact.json",
        dataset_id="dataset-A",
    )

    try:
        adapter.build_payload(artifact)
    except NotImplementedError as exc:
        assert "Spike scaffold" in str(exc)
    else:
        raise AssertionError("build_payload should be a stub in this spike")

    try:
        adapter.parse_result("wf-1", {"id": "obj-1"})
    except NotImplementedError as exc:
        assert "Spike scaffold" in str(exc)
    else:
        raise AssertionError("parse_result should be a stub in this spike")
