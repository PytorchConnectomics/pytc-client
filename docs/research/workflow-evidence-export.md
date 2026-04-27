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
- `bundle_directory` and `bundle_manifest_path` for the durable local export
- `copied_artifacts` and `skipped_artifacts` so paper notes can distinguish
  bundled small artifacts from large path-referenced data

## Paper-note utility

The durable bundle directory contains `workflow-bundle.json`,
`artifact-paths.json`, `README.md`, and a `files/` directory for copied
artifacts below the configured copy limit. Large files remain referenced by
absolute path unless `PYTC_WORKFLOW_BUNDLE_COPY_MAX_BYTES` is raised.

`server_api.workflows.evidence_export` provides a deterministic summary shape:

- `stage_progression_summary`
- `agent_proposal_approval_summary`
- `key_event_timeline_snippet`

Use this when exporting workflow evidence into local research logs for manuscript drafting.
