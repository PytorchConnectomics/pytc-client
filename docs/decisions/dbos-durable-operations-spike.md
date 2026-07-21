# DBOS Durable Operations Spike

- **Date:** 2026-07-21
- **Status:** Conditional go for a Postgres-backed integration prototype; no-go for production-route integration
- **Library evaluated:** `dbos[aiosqlite]==2.28.0`
- **Production code changed:** None

## Question

Can DBOS replace the process-global job state used by training and inference while
preserving the product-facing `WorkflowOperation` lifecycle: idempotent submission,
durable progress, cancellation, and restart recovery?

## Prototype

The isolated implementation lives in `spikes/dbos_operation`. It models a heavy
operation as a queued DBOS workflow containing checkpointed steps. Each step writes
an idempotent external marker representing a compute-chunk side effect. The workflow
publishes an `operation_progress` DBOS event containing the workflow ID, correlation
ID, completed and total step counts, normalized progress, and status.

The runner supports four operations without registering a production route:

```bash
uv run python scripts/run_dbos_operation_spike.py execute \
  --database /tmp/pytc-dbos.sqlite \
  --workspace /tmp/pytc-dbos-work \
  --workflow-id workflow-1 \
  --correlation-id request-1 \
  --duplicate-submission

uv run python scripts/run_dbos_operation_spike.py status \
  --database /tmp/pytc-dbos.sqlite --workflow-id workflow-1

uv run python scripts/run_dbos_operation_spike.py cancel \
  --database /tmp/pytc-dbos.sqlite --workflow-id workflow-1

uv run python scripts/run_dbos_operation_spike.py recover \
  --database /tmp/pytc-dbos.sqlite --workflow-id workflow-1
```

Automated evidence is produced by:

```bash
uv run pytest -q tests/test_dbos_operation_spike.py
```

Current result: **4 passed in 21.75 seconds** on Python 3.11 with a local SQLite
system database.

## Gates

| Gate | Required evidence | Result |
| --- | --- | --- |
| Runtime compatibility | Installs on the repository's Python 3.10-3.11 range | **Pass.** DBOS 2.28.0 declares Python >=3.10; the spike ran on 3.11. |
| Idempotent submission | Submitting the same workflow ID twice executes one workflow and one set of external markers | **Pass.** Both handles have the same ID; every marker is written once. |
| Durable progress | Progress is queryable outside the worker and remains available after completion or process death | **Pass.** `DBOS.set_event` progress is read through `DBOSClient`. |
| Queued cancellation | Cancelling enqueued work removes it before any external effect | **Pass.** Status becomes `CANCELLED`; no marker directory is created. |
| Running cancellation | Cancellation stops work at a documented durable boundary | **Pass with constraint.** Cancellation preempts at the next step boundary; it does not interrupt an ordinary blocking synchronous step. |
| Single-server restart | A killed process resumes from its last completed step without repeating that step's external effect | **Pass.** A replacement with the same executor identity recovers the `PENDING` workflow and completes the remaining markers. |
| Mid-step crash safety | Killing a process during a non-transactional external side effect cannot duplicate or corrupt that effect | **Not proven.** The test kills after the step and progress event are durable. Production steps still require idempotent outputs or transactional integration. |
| Postgres and multiple executors | Recovery, queue concurrency, and cancellation work with the intended production topology | **Not run; production gate fails.** SQLite is explicitly a development/test backend. |
| PyTC subprocess control | Training/inference subprocesses are killed, reaped, and reconciled correctly on cancel/restart | **Not run; production gate fails.** A blocking `Popen` step is not sufficient. |
| Product-state projection | DBOS state and `WorkflowOperation` cannot diverge under crashes | **Not designed; production gate fails.** A single source of truth and projection strategy is required. |

## Findings

1. DBOS workflow IDs directly provide the idempotency behavior currently implemented
   around `WorkflowOperation.idempotency_key`.
2. DBOS events are a good fit for durable progress and correlation data. They avoid
   writing a high-frequency progress stream into the main workflow table.
3. Queue concurrency maps well to GPU/CPU resource limits without a separate broker.
4. Recovery ownership is operationally significant. In the local single-server
   setup, the replacement process must reuse the interrupted executor identity.
   Multiple live executors require a production recovery strategy rather than PID-
   derived identities.
5. DBOS cancellation is cooperative at workflow/step boundaries. Immediate training
   cancellation needs a preemptible async step or a short polling supervisor around
   the subprocess, including process-group termination and output reconciliation.
6. DBOS does not make arbitrary filesystem or model-training side effects exactly
   once. Those effects must remain idempotent. The spike demonstrates this with
   exclusive marker creation.

## Decision

**Do not mount DBOS into the FastAPI production routes on this branch.** The local
prototype passes the behavioral gates it can honestly exercise, but the Postgres,
multi-executor, subprocess cancellation, and state-projection gates remain open.

Proceed with one additional, bounded integration phase only if Postgres is accepted
as backend infrastructure:

1. Run this suite against Postgres with two executor processes and forced worker
   loss.
2. Implement a supervised synthetic subprocess step and prove cancel/restart process
   cleanup before using real training.
3. Keep `WorkflowOperation` as the user-facing read model while DBOS owns execution,
   and update that read model through an idempotent projection keyed by DBOS workflow
   ID. Do not dual-write independent lifecycle transitions.
4. Use stable IDs such as
   `workflow:{workflow_id}:operation:{operation_id}:attempt:{attempt}` and retain the
   request correlation ID in progress events.
5. Integrate one operation type behind a feature flag, starting with evidence export
   or evaluation rather than GPU training.

The go/no-go after that phase is straightforward: all four currently failing gates
must pass before a production endpoint submits DBOS work.

## Primary References

- [DBOS Python workflows and workflow-ID idempotency](https://docs.dbos.dev/python/tutorials/workflow-tutorial)
- [DBOS queues and concurrency](https://docs.dbos.dev/python/reference/queues)
- [DBOS cancellation and resume semantics](https://docs.dbos.dev/python/tutorials/workflow-management)
- [DBOS workflow events for progress](https://docs.dbos.dev/python/tutorials/workflow-communication)
- [DBOS SQLite and Postgres guidance](https://docs.dbos.dev/python/tutorials/database-connection)
- [DBOS workflow recovery](https://docs.dbos.dev/production/workflow-recovery)
