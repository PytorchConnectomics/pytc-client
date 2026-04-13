from server_api.workflow.cave_adapter import CaveAdapter, CavePayload, WorkflowArtifact


def test_workflow_artifact_contract() -> None:
    artifact = WorkflowArtifact(
        artifact_id="artifact-1",
        artifact_type="synapse_annotations",
        payload={"rows": [{"id": 1}]},
        metadata={"project": "demo"},
    )

    assert artifact.artifact_id == "artifact-1"
    assert artifact.payload["rows"][0]["id"] == 1


def test_cave_payload_contract() -> None:
    payload = CavePayload(
        table_name="synapse_table",
        records=[{"id": 1, "confidence": 0.92}],
        provenance={"source": "spike"},
    )

    assert payload.table_name == "synapse_table"
    assert payload.records[0]["confidence"] == 0.92


def test_adapter_stubs_are_explicitly_unimplemented() -> None:
    adapter = CaveAdapter()
    artifact = WorkflowArtifact(
        artifact_id="artifact-2",
        artifact_type="mesh_summary",
        payload={"rows": []},
    )

    try:
        adapter.to_cave_payload(artifact)
    except NotImplementedError as exc:
        assert "Spike scaffold only" in str(exc)
    else:
        raise AssertionError("to_cave_payload should remain unimplemented in spike")

    payload = CavePayload(table_name="mesh_table", records=[])

    try:
        adapter.publish(payload)
    except NotImplementedError as exc:
        assert "Spike scaffold only" in str(exc)
    else:
        raise AssertionError("publish should remain unimplemented in spike")
