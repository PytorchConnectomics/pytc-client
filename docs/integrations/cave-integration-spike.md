# CAVE Integration Spike (Non-invasive)

## Purpose and target use case

This spike defines how the existing workflow artifacts produced by this app could be transformed into **CAVE-compatible payloads** for downstream visualization and annotation pipelines, while preserving current behavior.

Target use case in this app:
- A workflow route produces internal artifacts (e.g., dataset IDs, segmentation IDs, metadata blobs, and coordinate references).
- An explicit future integration step (not in default execution path) invokes a CAVE adapter to:
  1. normalize workflow artifacts into a CAVE request model,
  2. submit or hand off payloads to a CAVE-facing client,
  3. map CAVE responses back into app-level integration results.

Non-goal for this spike:
- No live CAVE API calls.
- No authentication or network wiring.
- No changes to existing routes, services, or startup behavior.

## Expected adapter inputs and outputs

### Input contract (adapter-facing)

Expected input object fields for conversion:
- `workflow_id: str` — stable workflow/run identifier.
- `artifact_uri: str` — URI/path to workflow-produced artifact.
- `dataset_id: str` — source dataset identifier used by this app.
- `segmentation_id: str | None` — optional segmentation or object collection handle.
- `point_xyz: tuple[float, float, float] | None` — optional spatial anchor.
- `metadata: dict[str, object]` — passthrough metadata for provenance.

### Output contract (adapter-facing)

Expected output object fields after conversion from CAVE-like response:
- `workflow_id: str` — original workflow ID echoed for correlation.
- `cave_object_id: str` — external object/resource identifier.
- `status: str` — normalized adapter status (`"ready"`, `"pending"`, `"error"`).
- `detail: dict[str, object]` — provider-specific details retained for debugging.

## Mapping: workflow artifacts → CAVE concepts

| App workflow artifact | CAVE concept | Notes |
|---|---|---|
| `dataset_id` | CAVE `datastack` / dataset namespace | one-to-one candidate mapping; final naming TBD |
| `segmentation_id` | CAVE segmentation/table reference | may map to a root ID table depending on deployment |
| `point_xyz` | CAVE spatial query point | coordinate frame assumptions must be validated |
| `artifact_uri` | CAVE payload provenance reference | used for traceability, not transport itself |
| `metadata` | CAVE annotation/provenance fields | allow selective pass-through with allowlist |

## Proposed integration flow (future, explicit path only)

1. Existing workflow completes artifact generation exactly as today.
2. Optional integration entrypoint calls `CaveWorkflowAdapter.build_payload(...)`.
3. A future network client (not part of this spike) sends payload to CAVE.
4. Optional integration entrypoint calls `CaveWorkflowAdapter.parse_result(...)`.
5. Caller decides whether/how to persist mapped result.

Because steps 2–5 are opt-in and not wired into current routes, runtime behavior remains unchanged.

## TODOs and assumptions

### Auth assumptions (TODO)
- TODO: define auth mode (service account token vs user-delegated token).
- TODO: define secure token source (secret manager / env var injection policy).
- TODO: define token refresh and expiration handling contract.

### Network assumptions (TODO)
- TODO: identify CAVE endpoint base URL(s) per environment.
- TODO: define retry/backoff and timeout defaults for network client.
- TODO: define circuit-breaker behavior for upstream CAVE outages.

### Deployment assumptions (TODO)
- TODO: decide whether adapter + client run in API container or async worker.
- TODO: define feature flag gating and rollout plan (staging → production).
- TODO: define observability requirements (structured logs, metrics, tracing).

## Actionable next steps

1. Confirm canonical mapping for `dataset_id`, `segmentation_id`, and coordinate frame with platform owners.
2. Add an explicit feature flag and non-default route hook for integration execution.
3. Implement a separate CAVE client module with auth/network concerns isolated from adapter mapping logic.
4. Add integration tests with mocked CAVE responses and failure scenarios.
5. Prepare deployment runbook covering credentials, endpoints, and rollback steps.
