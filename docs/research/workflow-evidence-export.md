# Workflow Evidence Export

Use the workflow utilities to generate stable evidence summaries for paper notes and analysis.

## Primary endpoints

- `GET /api/workflows/{workflow_id}/metrics`
- `POST /api/workflows/{workflow_id}/export-bundle`

## Bundle schema highlights

`export-bundle` returns:

- `schema_version` (`workflow-export-bundle/v1`)
- `workflow_id`
- `session_snapshot` (current workflow state)
- `events` (chronologically ordered)
- `artifact_paths` (`[{ path, exists }]`)

## Paper-note utility

`server_api.workflows.evidence_export` provides a deterministic summary shape:

- `stage_progression_summary`
- `agent_proposal_approval_summary`
- `key_event_timeline_snippet`

Use this when exporting workflow evidence into local research logs for manuscript drafting.
