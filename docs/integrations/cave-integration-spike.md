# CAVE Integration Spike (Non-invasive)

## Objective
Define a **CAVE-compatible data flow** for PyTC Client that can be implemented incrementally without changing current runtime behavior.

This spike is documentation-first and establishes a contract for future work.

---

## Target use case in this app
Primary use case: allow a user to run existing PyTC workflows (training, inference, proofreading, and visualization handoff) while optionally publishing workflow artifacts to a CAVE-aligned backend for downstream analysis.

In practical terms:
- Users continue using current PyTC routes and UI exactly as they do today.
- A future, explicit integration path can transform local workflow outputs (predictions, masks, metadata, provenance) into CAVE-style entities.
- Teams that rely on CAVE tooling can consume PyTC results without changing PyTC core execution paths.

Non-goal for this spike:
- No live auth, network calls, or deployment wiring.
- No routing changes in existing server endpoints.

---

## Expected inputs and outputs

### Inputs (from current PyTC workflow artifacts)
1. **Run context**
   - run ID / job ID
   - timestamp
   - model/config reference
2. **Dataset references**
   - source image path(s)
   - optional chunk/volume coordinates
   - resolution metadata
3. **Inference / proofreading outputs**
   - segmentation or mask outputs
   - object-level summaries/statistics where available
4. **Provenance and annotations**
   - operator/user reference (if available)
   - comments or QC notes (if available)

### Outputs (CAVE-aligned payload expectations)
1. **Dataset/collection descriptor**
   - canonical dataset key
   - spatial metadata
2. **Versioned result artifact record**
   - result identifier tied to run context
   - linkage to upstream input dataset references
3. **Optional annotation payload(s)**
   - typed annotation entries linked to coordinates/objects
4. **Status envelope**
   - accepted/rejected/queued semantics (for future async transport)

---

## Mapping: PyTC workflow artifacts → CAVE concepts

| PyTC artifact / concept | CAVE-aligned concept | Mapping notes |
|---|---|---|
| Training/inference run ID | Version / operation reference | Preserve immutable run identifier for lineage. |
| Input image volume path + scale | Dataset / image source descriptor | Include voxel resolution and bounds when available. |
| Output mask / segmentation file | Segmentation payload reference | Publish as versioned result; avoid overwriting by default. |
| Detected objects / stats | Table/annotation-like records | Map each object to stable ID and geometric summary. |
| Proofreading edits | Annotation update set | Track editor and timestamp in provenance fields. |
| Config YAML path + hash | Metadata / provenance attachment | Enables reproducibility checks in CAVE consumers. |
| Runtime status/result message | Ingest status envelope | Normalize to queued/succeeded/failed taxonomy. |

---

## Suggested integration contract (future)
Introduce an **explicit opt-in adapter path** that is only invoked by future routes or background jobs, for example:
- `prepare_cave_payload(run_artifacts) -> CavePayload`
- `validate_cave_payload(payload) -> ValidationResult`
- `publish_to_cave(payload, transport) -> PublishResult`

Design constraints:
- Adapter must be import-safe and side-effect free.
- No network or auth dependency at import time.
- Existing endpoints continue untouched unless a new flag/route explicitly calls the adapter.

---

## Non-invasive rollout plan
1. **Phase 0 (this spike):** document contract and mappings (this file).
2. **Phase 1:** add inert adapter scaffolding with interface stubs only.
3. **Phase 2:** add offline payload generation and validation tests.
4. **Phase 3:** add optional transport implementation behind explicit feature flag.
5. **Phase 4:** wire opt-in route or async task that calls adapter.

---

## TODOs (auth/network/deployment assumptions)

### Auth TODOs
- Define service-to-service auth model (token issuer, rotation policy, scopes).
- Decide whether end-user identity is propagated or service account is used.
- Specify failure behavior for auth expiration (retry vs fail-fast).

### Network TODOs
- Define allowed egress targets and timeout/retry policy.
- Decide sync vs async delivery semantics for large artifacts.
- Define payload size limits and chunking/compression behavior.

### Deployment TODOs
- Define environment variables/secrets required for CAVE endpoints.
- Choose deployment topology (in-process transport vs worker queue).
- Add observability requirements (structured logs, metrics, tracing IDs).

---

## Actionable next steps
1. Create `server_api/workflow/cave_adapter.py` with pure interface stubs and typed payload models.
2. Add `tests/test_cave_adapter_contract.py` to lock down:
   - no side effects on import,
   - deterministic payload mapping from fixture artifacts,
   - explicit invocation requirement (not called in default app path).
3. Add a feature flag proposal (`PYTC_ENABLE_CAVE_ADAPTER=false` default) for a future opt-in route.
4. Review mapping table with CAVE stakeholders and finalize required fields.

This keeps current behavior unchanged while preparing a low-risk implementation path.
