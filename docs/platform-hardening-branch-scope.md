# Platform Hardening Branch Scope

Branch: `agent/platform-hardening`

Base: `origin/main` at `a991b1b`

## Objective

Establish the shared technical substrate needed for a recoverable, resource-bounded,
agent-mediated segmentation loop. This branch hardens existing workflow behavior;
it does not redesign the participant workflow or replace PyTorch Connectomics.

## In Scope

1. A structured API error contract with stable machine codes, user-facing recovery
   guidance, request correlation, and a consistent frontend representation.
2. Application-level frontend failure boundaries and explicit retry/recovery states
   for failures that currently disappear into transient notifications.
3. A bounded volume access contract that separates metadata inspection and region
   reads from full materialization across supported volume formats.
4. Persisted operation records for long-running work, including terminal failure and
   cancellation states, idempotency, and correlation to workflow evidence.
5. A typed agent action registry that defines allowed inputs, risk, approval policy,
   and execution ownership independently of language-model intent routing.
6. Focused tests and compatibility shims that preserve the current closed-loop smoke
   path while new primitives are adopted incrementally.

## Out of Scope

- Database sharding or horizontal multi-tenant scaling.
- A mandatory bulk conversion of existing datasets.
- Replacing Neuroglancer, PyTorch Connectomics, or every existing API route.
- Full migration of all subprocess execution into a distributed worker system.
- A visual redesign unrelated to loading, failure, recovery, or task state.
- Removing existing workflow evidence records or approval history.

## Architectural Invariants

- Base image and imported label artifacts remain immutable by default.
- Volume callers must be able to inspect metadata and request a bounded region without
  materializing the complete volume.
- Risky agent actions remain approval-gated and must resolve through a registered,
  typed action definition.
- The browser may perform navigation and presentation effects; domain execution and
  durable state transitions belong to the server.
- Operation state must survive a server restart even before subprocess reattachment is
  implemented.
- User-visible failures include a stable code, recovery guidance, and request ID while
  technical details remain available for diagnosis.

## Acceptance Criteria

- Backend tests cover error serialization, volume metadata/region reads, operation
  lifecycle transitions, and registered agent action validation.
- Frontend tests cover normalized API failures, the application error boundary, and a
  user-triggered recovery path.
- Existing workflow, EHTool, runtime, and agent proposal tests remain green or receive
  narrowly justified compatibility updates.
- The production frontend build completes.
- No new critical path depends on full-volume NumPy materialization when only metadata
  or a subvolume is required.
- New agent proposal types cannot silently bypass registry validation or approval
  policy.

## Delivered

- Shared FastAPI error envelopes preserve legacy `detail` values while adding stable
  codes, categories, retry guidance, recovery actions, and request IDs. The React
  client normalizes transport and API failures and has a root recovery boundary.
- `VolumeStore` separates metadata and region access from NumPy materialization for
  HDF5, TIFF/OME-TIFF, NPY/NPZ, Zarr/N5, NIfTI, and MRC sources. Neuroglancer now
  serves 3D image and label chunks from those stores and closes backing resources
  when retained viewers expire or are evicted.
- `WorkflowOperation` persists queued, running, succeeded, failed, and cancelled
  work with idempotency, correlation, leases, heartbeats, progress, and cancellation
  requests. Approved training commands create a per-attempt operation and commit
  command/operation state together.
- Agent effects resolve through strict, discriminated runtime and workflow action
  schemas. The registry owns risk, approval, execution-owner, and specialist policy;
  unknown proposal types, effect keys, and nested action parameters are rejected.

## Verification

- Backend: full suite passes (`278 passed`, plus five subtests), including an actual
  on-demand Neuroglancer chunk read from HDF5-backed image and label sources.
- Frontend: all 26 suites pass (`138 passed`).
- Production frontend build succeeds. Existing React hook and bundle-size warnings
  remain unchanged.

## Follow-On Work

This branch intentionally creates migration points. A subsequent branch should:

1. Synchronize worker completion, failure, and cancellation into long-running training
   and inference operations; current training-command success means the worker accepted
   submission.
2. Add a frontend task center backed by operation records so reconnecting clients can
   resume progress and cancellation state.
3. Materialize multiscale OME-Zarr for repeated large-volume access and preprocess 4D
   prediction tensors into 3D label volumes before Neuroglancer launch.
4. Convert EHTool proofreading persistence from retained full arrays to chunk-aligned
   correction overlays; its editing model still requires complete mutable volumes.
5. Move remaining browser-orchestrated runtime launches behind server command handlers
   while keeping navigation and form-prefill effects browser-owned.
