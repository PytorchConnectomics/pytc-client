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
- `artifact_paths`
- `bundle_directory` and `bundle_manifest_path` for the durable local export
- `copied_artifacts` and `skipped_artifacts`
- `copy_settings` with effective max-size configuration
- `project_memory_summary`

## Policy-aware artifact metadata

`artifact_paths` entries now include structured policy and reference fields:

- `copy_policy`
  - `allow_copy`
  - `reason` (`withheld_reference`, `ground_truth_reference_outside_dataset`,
    `external_reference_path`, `metadata_restriction`, `size_limit`, etc.)
  - `policy_code` (`default`, `withheld_reference`,
    `ground_truth_reference_outside_dataset`, `external_reference_path`, ...)
- `copy_mode` (for skipped artifacts):
  - `missing` (path does not exist)
  - `not_a_file`
  - `manifest_only`
  - `policy` (policy-only references)
  - `size_limit`
- `reference_scope`
  - `is_reference_only`
  - `reference_reason` (`withheld_reference`, `ground_truth_reference_outside_dataset`)
  - `reference_key`
- provenance fields:
  - `source_type` (`session_snapshot`, `event`, `artifact`, ...)
  - `source_key` / `source_parent_key`
  - `sources` (all contributing sources for shared paths)

### Policy precedence

When multiple sources emit the same path, path policy reasons merge with this order:

1. `withheld_reference`
2. `ground_truth_reference_outside_dataset`
3. `external_reference_path`
4. metadata restriction / default fallback

This keeps held-out and ground-truth restrictions dominant over generic external-reference tagging.

Reference-only paths are still emitted as skipped artifacts in `skipped_artifacts` with:

- `reason = "reference_only_policy"`
- `copy_mode = "policy"`
- `copy_policy` preserving the strongest reason (`withheld_reference` preferred where appropriate)

`artifact_paths` and `skipped_artifacts` are therefore paper-grade enough to recover exact export intent without ad-hoc assumptions.

## Paper-note utility

The durable bundle directory contains:

- `workflow-bundle.json`
- `artifact-paths.json`
- `README.md`
- `files/` (copied payloads)

`copy_manifest_only=true` writes only path metadata and manifest files, skipping bytes.

The same `copy_mode` values above and raw/max-size fields appear in skipped records:

- `size_bytes`
- `copy_limit_bytes`
- `raw_copy_max_bytes`

## Evidence export summary shape

`server_api.workflows.evidence_export` now includes stricter, linked summary shapes:

- `stage_progression_summary`
- `agent_proposal_approval_summary`
- `agent_proposal_approval_links`
- `agent_proposal_approval_graph`
- `user_status_changes`
- `model_context`
- `project_memory_summary`
- `key_event_timeline_snippet`

`agent_proposal_approval_graph` is ordered by proposal creation and is intended to be machine-readable:

- `proposal`: `event_id`, `summary`, `action`, `params`, `stage`, `actor`
- `approval`: approval event linkage and `approval_payload`
- `action_events`: proposal→action edges (e.g., `training.run_approved`, `agent.client_effects_approved`, `retraining.staged`)
- `commands`: command records created from action execution
- `runs`: model runs linked to proposals/actions with structured `progress_events`

`project_memory_summary` is included as a compact paper-oriented digest with `schema_version` `pytc-project-memory-summary/v1`.
It includes `workflow_id`, `workflow_stage`, `workflow_title`, `dataset_path`, and
artifact/run/version/plan/command event counts.

`agent_proposal_approval_links` includes explicit proposal-action-approval links:

- `proposal_event_id`
- `approval_event_id`
- `approval_status`
- `action` (original proposal action)
- `params` (original proposal params)

`agent_proposal_approval_graph` includes a per-proposal chain:

- `proposal`: `event_id`, `summary`, `action`, `params`, `stage`, `actor`
- `approval`: `event_id`, `status`, `stage`, `actor`, `approval_payload`
- `action_events`: event-level progress into action staging
- `commands`: `command_id`, `command_type`, `status`, `actor`,
  `source_event_id`, `approval_event_id`, timing fields
- `runs`: `run_id`, `run_type`, `status`, artifact/config references,
  `progress_events` (with `event_type`, `run_type`, `run_id`, `actor`, `created_at`, etc.)

Use this when exporting workflow evidence into local research logs for manuscript drafting.
