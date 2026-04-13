# Workflow Evidence Export

Use this utility to create a stable JSON summary for paper/research notes from a seeded workflow fixture.

## Output schema

The exporter writes a JSON document with a stable top-level version key:

- `version` — currently `1.0`
- `workflow_id`
- `stage_progression_summary`
- `agent_proposal_approval_summary`
- `key_event_timeline_snippet` (machine-readable list)

## Run the export

```bash
uv run python -m server_api.workflow.evidence_export \
  --workflow-json path/to/workflow-fixture.json \
  --output docs/research/exports/workflow-evidence.json
```

## Where output is written

The `--output` path is written exactly as provided. Parent directories are created automatically.

For research notes, keep exports under:

- `docs/research/exports/`

Example output target:

- `docs/research/exports/workflow-evidence.json`
