# Preliminary Agentic Workflow Report Triage

Date: 2026-05-27

## What This Is

This is a short engineering triage of `docs/research/agentic-workflow-formalization-report.md` while a fuller ChatGPT Deep Research pass is running.

The preliminary report is useful, but it was produced quickly. Treat it as an implementation-facing hypothesis document, not as final literature support for the paper.

## Bottom Line

The report's main direction is strong enough to act on:

> Build the assistant as a workflow-aware, approval-gated project operator. Chat is the conversational surface. Project memory is the source of truth. Action cards are the bridge from intent to bounded execution. Evidence events are the provenance layer.

This matches what the prototype failures have shown in practice:

- when the agent lacks fresh project state, it becomes generic;
- when project progress is not canonical, training/proofreading/inference choices drift;
- when action cards do not fully stage paths/artifacts, approval appears to do nothing;
- when onboarding starts from a blank prompt, biologists are stranded;
- when evidence is not recorded, the paper has weak system claims.

## What Is Solid Enough To Implement Now

### 1. Yixiao Harness And Demo Contract

Already started and should continue.

The repo now has:

- `scripts/run_yixiao_case_study_smoke.py`
- `docs/manual-yixiao-case-study-demo.md`

These directly support the report's recommendation that case studies need repeatable evidence, not vibes.

Next concrete extensions:

- add a proofread/promote smoke path for `5_1` or `5_2`;
- add a no-checkpoint inference blocker check for `6_1` / `6_2`;
- add a post-checkpoint inference proposal smoke once a checkpoint exists;
- add evidence-bundle export validation for the Yixiao workflow.

### 2. Canonical Project Memory Read Model

The preliminary report correctly identifies this as the central technical move.

Current app already has `GET /api/workflows/{workflow_id}/memory`, but it should be hardened into the shared contract used by:

- Assistant;
- Progress;
- Train Model;
- Run Model;
- Proofread;
- evidence export.

Immediate implementation target:

- version the memory schema explicitly;
- include freshness markers for project tree, progress, runtime, proofreading, and assistant context;
- include source/evidence for each project fact;
- include canonical active volume set;
- include selected training/inference candidates derived from volume states;
- add tests around MitoEM2 and Yixiao fixtures.

### 3. Volume State Vocabulary Migration

The report's proposed vocabulary is more expressive than the current prototype.

Current legacy states:

- `ground_truth`
- `needs_proofreading`
- `missing_segmentation`
- `ignored`

Proposed canonical states:

- `image_only`
- `draft_segmentation`
- `needs_proofreading`
- `proofread_ground_truth`
- `training_candidate`
- `queued_for_inference`
- `prediction_ready`
- `ignored`

Do not switch the whole UI in one risky pass. Add aliases first:

| Legacy | Canonical Alias |
|---|---|
| `ground_truth` | `proofread_ground_truth` |
| `missing_segmentation` | `image_only` |
| `needs_proofreading` | `needs_proofreading` |
| `ignored` | `ignored` |

Immediate implementation target:

- expose canonical state and display label in project memory;
- keep legacy fields for compatibility;
- update agent decision logic to reason in canonical terms;
- update Progress copy so users see normal wording, not internal enum names.

### 4. Typed Action Proposal Envelope

The report is right that action semantics are split across too many surfaces.

Current sources include:

- chat actions;
- command blocks;
- proposal events;
- direct client effects;
- runtime actions;
- workflow commands.

Immediate implementation target:

- define a `WorkflowActionProposal` JSON schema in backend docs/code;
- make agent-generated cards include a stable `proposal_type`, `risk_level`, `affected_volume_ids`, `inputs`, `outputs`, `preconditions`, `evidence_basis`, and `postconditions`;
- keep frontend rendering compatible with current cards, but normalize server output.

Do this before large new agent behaviors. It will prevent another "Approve does nothing" regression.

### 5. Guided Context Elicitation

The report's onboarding recommendation is consistent with user feedback.

Immediate Yixiao-specific version:

- after mount, show detected facts:
  - "I found XRI/CytoTape fibre data";
  - "10 volumes: 6 GT, 2 draft masks, 2 image-only";
  - "voxel size 40 x 16.3 x 16.3 nm";
  - "training policy: use confirmed GT only";
  - "config: app-compatible TapeReader sanity config";
- ask short confirmation questions, not one blank textarea;
- persist corrections as project memory confirmations.

This can be implemented before the full generalized version.

## What Needs Deep Research Validation

Do not treat these as final until the fuller pass returns:

### 1. Third Case Study Choice

The preliminary report recommends CREMI-style affinity-heavy neuron segmentation. That is plausible, but the implementation risk is high.

Deep research should validate whether the paper is better served by:

- CREMI/SNEMI3D for workflow diversity and connectomics realism;
- Lucchi++ for a stable onboarding case;
- NucMM or another non-mito case for breadth;
- keeping the third case as future work.

For tomorrow/prototype stability, do not block Yixiao work on this.

### 2. Literature Completeness

The cited areas are directionally correct:

- Horvitz mixed initiative;
- Amershi HAI guidelines and interactive ML;
- ilastik / CellProfiler / napari / Neuroglancer / WEBKNOSSOS / VAST;
- CAVE / provenance / OME-Zarr / REMBI;
- Codex / Claude Code / Copilot as product-pattern analogies.

But the quick report should be audited for:

- missing primary HCI sources;
- overreliance on product docs;
- exact claims about CAVE/WEBKNOSSOS/VAST;
- current dates and versions;
- better workflow/provenance sources.

### 3. Evaluation Design

The proposed participant tasks are good starting points, but deep research should strengthen:

- baselines;
- measures;
- study size;
- what evidence supports TOCHI versus a demo/system paper;
- how to avoid implying segmentation-accuracy improvements.

## Engineering Work To Do While Deep Research Runs

Prioritized for the Yixiao-only lock-in:

1. **Proofreading roundtrip for Yixiao draft masks**
   - Open `5_1` or `5_2`.
   - Save or mock a correction artifact.
   - Promote to `proofread_ground_truth`.
   - Verify Progress and agent training subset update from 6 GT to 7 GT.

2. **Inference blocker and target proposal**
   - Ask agent to segment `6_1` / `6_2` before a checkpoint exists.
   - It should explain the checkpoint blocker and offer training/checkpoint registration.
   - Once a checkpoint exists, it should propose inference on exactly `6_1` / `6_2`.

3. **Evidence bundle export for Yixiao**
   - Export workflow memory, volume states, viewer events, training proposal, approvals, subset manifest, and smoke report path.
   - Add a validator that confirms these records exist.

4. **Yixiao guided intake card**
   - Replace any blank project-context textarea for this fixture with detected facts and confirm/edit controls.
   - Persist confirmations.

5. **Action card cleanup**
   - Make the training card display:
     - 6 included GT volumes;
     - 2 draft masks excluded;
     - 2 image-only targets after training;
     - config;
     - output/log path;
     - approval behavior.
   - Hide giant paths behind details.

6. **Project memory hardening**
   - Add freshness fields.
   - Add source/evidence for project facts.
   - Add canonical state aliases.
   - Add tests that Yixiao memory remains stable after refresh.

## Strong Claims We Can Make After Current Work

If the Yixiao harness and current workflow remain stable, we can safely claim:

- the system can mount and inspect a real XRI/TapeReader project fixture;
- it tracks volume-level workflow state across GT, draft masks, and image-only targets;
- it opens selected raw/mask pairs in Neuroglancer with project voxel scale;
- it turns a natural-language training request into an approval-gated multi-volume training proposal;
- it preserves excluded draft masks and image-only targets in the proposal;
- it validates worker-side training subset path resolution before launch.

## Claims To Avoid For Now

Avoid claiming:

- the system reproduces TapeReader performance;
- the current proofread UI fully supports production-grade fibre correction;
- the current agent can visually inspect image quality;
- the current app has complete project-memory invalidation;
- the workflow generalizes across all bioimage segmentation tasks;
- the assistant improves segmentation accuracy.

## Recommended Next Engineering Move

Do the Yixiao proofreading roundtrip next.

Reason:

- It directly tests the heart of the paper story: human correction changes project state, and the agent uses that updated state in the next training proposal.
- It will expose whether Progress, Proofread, Assistant, and Train Model are actually coordinated or just separately plausible.
- It produces a clean paper/demo moment: 6 GT becomes 7 GT after a human review decision.
