# CAVE Integration Spike (Non-invasive)

## Purpose
This spike defines a **CAVE-compatible data flow contract** for future export of
workflow artifacts produced by this app, without changing any current runtime
behavior or existing routes.

## Target use case in this app
Primary target: export app-generated workflow artifacts (for example synapse
annotation outputs, mesh/segment summaries, or inference-derived tabular
results) into CAVE-aligned table payloads for downstream analysis and shared
annotation ecosystems.

This spike intentionally does **not** perform any live CAVE writes.

## Expected inputs and outputs

### Input: workflow artifact
A workflow artifact is expected to include:
- `artifact_id` (string): unique identifier in this app
- `artifact_type` (string): category used for mapping rules
- `payload` (object): app-native structured data
- `metadata` (object, optional): project/run context and provenance

### Output: CAVE payload
A CAVE payload is expected to include:
- `table_name` (string): target CAVE table identifier
- `records` (array of objects): normalized row-level entries
- `provenance` (object): transformation metadata

## Mapping from workflow artifacts to CAVE concepts

| App workflow concept | CAVE concept | Notes |
| --- | --- | --- |
| `artifact_id` | provenance field (`source_artifact_id`) | retain source traceability |
| `artifact_type` | table routing key | determines target `table_name` |
| `payload.rows[*]` | `records[*]` | row-level normalization and field mapping |
| app run metadata | provenance fields | include model version, timestamp, operator |

### Proposed mapping flow
1. Receive a `WorkflowArtifact` from an explicit, non-default integration path.
2. Select table mapping logic by `artifact_type`.
3. Transform artifact payload rows into normalized CAVE records.
4. Attach provenance data from artifact and runtime context.
5. Return `CavePayload` for optional downstream publisher step.

## Non-invasive guardrails
- Adapter code lives in `server_api/workflow/cave_adapter.py` and is not wired
  into existing startup, routes, or default workflow execution.
- Adapter methods are stubs and raise `NotImplementedError`.
- No network calls, auth dependencies, or deployment config are active.

## TODO assumptions to resolve before implementation
- **Auth TODO:** decide token model (service token vs user token), rotation, and
  secret storage location.
- **Network TODO:** define endpoint discovery, TLS requirements, retry/backoff,
  and timeout policy.
- **Deployment TODO:** define environment config contract, feature flags, and
  rollback strategy for staged rollout.

## Actionable next steps
1. Finalize per-`artifact_type` mapping schemas and validation rules.
2. Add contract tests for each mapping variant with realistic fixture payloads.
3. Implement publisher client behind an explicit feature flag.
4. Add integration tests with mocked transport/auth layers.
5. Add observability for export attempts, latency, and error classes.
