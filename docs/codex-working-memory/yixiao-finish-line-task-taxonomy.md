# Yixiao Finish-Line Technical Taxonomy

Last updated: 2026-06-04

This document defines the acceptance gates for the Yixiao / TapeReader XRI case
study and maps each gate to what the prototype can claim during a one-hour
walkthrough versus what requires a full closed-loop run.

## Current Claim Tiering

### Claim Tier A (today, safe for talk demos)

The prototype can claim workflow coordination on this fixture:

- mounted-project inspection and grounded context,
- grounded volume-state accounting (ground-truth / draft / image-only),
- bounded agent proposal behavior with explicit approval gating.

Current evidence comes from:

- 10-volume fixture mount (`6` ground-truth, `2` draft, `2` image-only),
- stable context (`tapereader_xri_fiber`, `data/raw`, `data/seg`,
  `TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`),
- proposal flow from user asks like "train on fully good masks,"
- smoke-based restoration and promotion checks.

### Claim Tier B (not yet supported as a paper result)

The system should not claim model-quality or closed-loop performance until
all of the following are evidenced by app-executed artifacts:

1. training run completion record,
2. checkpoint/model version registration,
3. post-training inference on image-only targets,
4. evaluation against held-out truth,
5. exported evidence linking these steps end-to-end.

## One-Hour Go/No-Go Acceptance Matrix (Yixiao)

For a live one-hour session, the protocol is `GO` only if every row is green.
`NO-GO` means the facilitator must pause and reset claim language.

| Gate | Explicit Pass Condition | Evidence Check |
| --- | --- | --- |
| Baseline project state | Baseline is exactly 10 volumes, `6/2/2` split, correct roots/config, project identified as Yixiao/XRI/CytoTape. | `--prepare-live`; project profile and progress assertions |
| Agent context | Assistant summary uses mounted workflow context, not stale dataset names or defaults. | `--prepare-live`; project context assertions; agent recommendation |
| Approval-gated training proposal | Training request creates a reviewable proposal, not auto-launch. | `--prepare-live`; recommendation/`agent-proposal` logs |
| Proofread promotion | Draft volume can be promoted and reflected in progress state. | `--exercise-promotion`; volume-status transition assertions |
| Closed-loop rehearsal | Rehearsal path can pair `6_1` / `6_2` predictions with withheld targets without in-project leakage. | `--closed-loop-rehearsal` |
| Real training/inference/evaluation artifacts | Terminal training/inference completion + checkpoint/version + evaluation entries exist. | model runs, model versions, evaluation results, bundle export |
| Export bundle | Evidence bundle returns with schema, artifact manifests, and copy-policy summary (including size-safe defaults). | `/api/workflows/{id}/export-bundle` |
| Live demo health | API/worker/Neuroglancer/worker routing/app log health checks are clean enough for launch, with temporary-load transients treated as WARN, not FAIL. | `inspect_demo_instance.py --json` |

### Acceptance interpretation

- `GO` requires the first six rows and rows 7 and 8 to pass for the live path.
- For row 8, treat `WARN` as expected operational noise (e.g., transient load or missing optional logs) and `FAIL` as a hard blocker.
- If `Real training/inference/evaluation artifacts` is `NO-GO`, the walkthrough stays at
  coordination-level claims and must explicitly state this limitation.
- If any health check is hard-fail (`api.health` down, `worker.url_mismatch`, critical
  app errors), treat as `NO-GO`.

## Case-Study Evidence Mapping

| Claim | Can claim today | Requires closed-loop evidence |
| --- | --- | --- |
| "workflow coordination" | yes | no |
| "approval-gated training proposal" | yes | no |
| "proofread promotion affects training readiness" | partial (status transition only) | full browser proofread edit/save/replay loop |
| "model converges/improves on TapeReader targets" | no | training + inference + evaluation artifacts |
| "closed-loop quality is measured on withheld labels" | no | rehearsal + real infer/eval records tied to model versions |

## Ready/Not-Ready Task Taxonomy

### Must be ready for the one-hour session

- smoke harness passes baseline and restore,
- promotion drill validates fixture state transitions,
- readiness and export checks are non-empty and pass smoke-level requirements,
- live health checks are non-blocking,
- runtime deployment observability is captured as expected values (worker URL, Neuroglancer port, public base) in one command:

```bash
.venv/bin/python scripts/inspect_demo_instance.py --api-base https://demo.seg.bio --json
```

- facilitator follows the claim boundary in the script.

### Must be explicit caveats (not blockers)

- no TapeReader barcode checkpoint in this fixture,
- no browser-level proofread edit quality claim from the current app loop,
- no full performance claim without real train/infer/eval evidence.

## 2026-06-04 Follow-Up Workstreams

This is the current subagent split for the second finish-line pass.

| Workstream | Owner | Scope | Success Condition |
| --- | --- | --- | --- |
| Closed-loop execution | Worker A | Operator-safe train/infer/evaluate runbook/helper, explicit holdout truth, short-run override scaffolding | A facilitator can see the exact commands or app steps required for a real short run, and the helper refuses accidental use of mounted labels for `6_1`/`6_2`. |
| Browser QA | Worker B | Browser-level smoke or documented automation gap | We can validate the user-visible path, including refresh/reopen and proposal readability, with a repeatable command or documented manual fallback. |
| Agent proposal UX | Worker C | Editable proposal-card fields, terminal state clarity, specialist agent visual labels | Users can adjust agent-filled values before approval and agent role labels/icons do not clip. |
| Memory/provenance | Worker D | Export completeness, artifact links, external holdout evidence | Evidence bundles contain the records needed to support workflow claims without relying on hidden chat state. |
| Deployment survivability | Worker E | Demo2 API restart/start/stop helper and health validation | The live demo can be restarted without brittle shell behavior or accidentally affecting other deployments. |
| Study readiness | Worker F | Go/no-go checklist and paper claim acceptance criteria | The team has a crisp matrix for what is demo-ready, what is caveated, and what remains before a stronger paper result. |

## Current Hard Gaps

These are the gaps still expected to remain after the second pass unless a worker
specifically closes them:

- **Real training runtime:** no completed Yixiao app-launched training run has
  been captured in the current evidence ledger.
- **Real inference runtime:** no checkpoint-backed inference outputs for `6_1`
  and `6_2` are registered as completed workflow runs.
- **Real evaluation record:** rehearsal validates the wiring, but real
  prediction-vs-holdout metrics still need a model/version-backed evaluation.
- **Browser proofread edit quality:** status promotion works, but the case study
  does not yet prove manual edits in the proofreading editor are biologically
  meaningful.
- **Commit hygiene:** the working tree is large and dirty; before paper/demo
  freeze, changes should be split into coherent commits.

## P0/P1 Alignment

P0 items are now acceptance gates in the matrix above and are required for
release gating of the Yixiao walk-through.

- **P0**
  - baseline restore and smoke health,
  - context fidelity and bounded assistant behavior,
  - proposal approvals,
  - promotion and continuity checks,
  - export copy policy enforcement,
  - operator visibility.

- **P1**
  - real train/infer/eval closure,
  - browser proofread edit/save loop with durable corrected artifacts,
  - scheduler-level production hardening and multi-user safety.

## Go / No-Go Summary

Go for the session if all one-hour gates pass and the presenter uses only
Tier A claims.
No-go if any hard gate fails or if Tier B claims are described as achieved results.
