# ChatGPT Deep Research Task: Verify And Strengthen The Agentic Segmentation Workflow Formalization

## Role

Act as a rigorous external research agent reviewing and extending an engineering report for seg.bio / PyTC Client, a web app for volumetric biomedical image segmentation workflows.

Your goal is **not** to produce a generic LLM-agent essay. Your goal is to independently verify, critique, and strengthen the proposed architecture for a workflow-aware assistant specialized for biomedical image segmentation.

The target system should be closer to Codex / Claude Code in workflow discipline, but specialized for segmentation projects: inspect a mounted project, maintain grounded project memory, propose bounded app actions, ask concrete context questions, execute approved routines, and keep the user oriented across visualization, proofreading, training, inference, evaluation, and evidence export.

## Primary Output

Write a final markdown research report that can replace or substantially improve:

`docs/research/agentic-workflow-formalization-report.md`

The report should be actionable for engineers and defensible for a systems/HCI paper.

## Important Limitation

You may not have direct access to the local filesystem. If local files are unavailable, do **not** pretend to inspect them. Use:

- public repository URLs;
- any code excerpts pasted into this prompt/session;
- uploaded files, if provided;
- web-accessible documentation and papers;
- explicit uncertainty labels where local verification is missing.

When local code inspection is unavailable, mark findings as:

- `Verified from public source`;
- `Verified from provided excerpt`;
- `Inferred from project description`;
- `Needs local verification`.

## Project Context

Primary public/demo deployment:

- https://demo.seg.bio

Primary repositories:

- PyTC Client / seg.bio app: https://github.com/PytorchConnectomics/pytc-client
- PyTorch Connectomics backend library: https://github.com/PytorchConnectomics/pytorch_connectomics
- TapeReader reference pipeline: https://github.com/LinghuLab/TapeReader

Current app modules:

- Files: mount and inspect project folders.
- Visualize: open image/mask volumes in Neuroglancer.
- Train Model: configure and launch PyTorch Connectomics training.
- Run Model: configure and launch inference.
- Progress: volume-level workflow tracking.
- Proofread: review and correct segmentation masks.
- Assistant: workflow-aware chat plus action cards.

The `Monitor` tab has been sunset. Runtime status should live near relevant action surfaces:

- training state in Train Model;
- inference state in Run Model;
- proofreading state in Proofread;
- project state in Progress / workflow overview.

## Current Engineering Problem

The assistant prototype is useful but not formal enough.

Known pain points:

- The agent sometimes answers from stale or incomplete project context.
- Project context is assembled from scanned files, manifests, workflow state, progress state, user chat, and runtime events.
- There is not yet one canonical project-memory contract shared by all app modules and the agent.
- Action cards exist, but the policy for proposing, asking, approving, executing, or refusing actions needs formalization.
- Initial setup can strand biologists in blank text boxes instead of guiding them through concrete detected project facts.
- The agent should inspect project state and ask targeted questions, but should not pretend to validate facts it cannot inspect.
- Visible chat should feel normal and concise, while inspection details should be available through progressive disclosure.
- Training, inference, and proofreading actions should be bounded app routines, not arbitrary shell execution.
- Long-running jobs and artifact mutations need durable provenance.
- The paper needs a defensible explanation of why this is a coherent human-agent workflow system, not a UI wrapped around an LLM.

## Case Studies

### Case Study 1: MitoEM / MitoEM2-Style Progress Workflow

Likely local fixture:

- `/home/weidf/demo_data/mitoem2_progress_demo`

Known/project-described workflow:

- EM/ssSEM mitochondria instance segmentation.
- Some volumes are confirmed ground truth.
- Some volumes have draft segmentations needing proofreading.
- Some volumes are image-only targets.
- The agent should train from confirmed/proofread ground truth and propose inference for image-only volumes.

Known fixture facts from a local manifest excerpt:

- 6 HDF5 smoke volumes.
- Initial split: 2 ground-truth, 2 needs-proofreading, 2 missing-segmentation/image-only.
- Voxel size: z,y,x = 30,8,8 nm.
- Config: `configs/MitoEM2-Pyra-Demo-BC.yaml`.
- Source links include:
  - https://huggingface.co/datasets/pytc/MitoEM2.0/tree/main
  - https://connectomics.readthedocs.io/en/latest/tutorials/mito.html

### Case Study 2: Yixiao / TapeReader XRI Fibre Workflow

Likely local fixture:

- `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`

Reference:

- TapeReader: https://github.com/LinghuLab/TapeReader
- Preprint: https://www.biorxiv.org/content/10.1101/2025.05.10.653182v1

Known fixture facts from a local manifest excerpt:

- 10 tracked XRI volumes.
- 6 confirmed ground-truth masks: `1`, `2`, `3`, `4_1`, `4_2`, `4_3`.
- 2 draft masks needing proofreading: `5_1`, `5_2`.
- 2 image-only inference targets: `6_1`, `6_2`.
- Active voxel spacing: z,y,x = 40,16.3,16.3 nm.
- App-compatible config: `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`.
- Paper-faithful config: `configs/TapeReader-Fiber-BCS-Original-Barcode.yaml`.
- Important requirement: preserve the distinction between paper-faithful TapeReader pipeline semantics and current app-compatible PyTC fallback config semantics.

### Case Study 3: To Recommend

Recommend the strongest third case for the paper and explain what agent/workflow behavior it exercises.

Candidate families:

- Lucchi++ for reliable onboarding/demo.
- SNEMI3D or CREMI for affinity-heavy connectomics.
- NucMM or another non-mitochondria volumetric segmentation workflow.

The recommendation should balance:

- paper value;
- implementation risk;
- diversity from MitoEM and TapeReader;
- ability to stress the project-memory/action/provenance model.

## Local Code Areas To Investigate If Accessible

If you can access the repo, inspect these areas and neighboring modules:

Backend:

- `server_api/workflows/router.py`
- `server_api/workflows/service.py`
- `server_api/workflows/db_models.py`
- `server_api/workflows/bundle_export.py`
- `server_api/workflows/volume_pairs.py`
- `server_api/auth/router.py`
- `server_api/auth/models.py`
- `server_api/main.py`

Frontend:

- `client/src/components/Chatbot.js`
- `client/src/components/chat/AssistantActionCard.js`
- `client/src/components/chat/AgentProposalCard.js`
- `client/src/contexts/WorkflowContext.js`
- `client/src/contexts/GlobalContext.js`
- `client/src/views/FilesManager.js`
- `client/src/views/Visualization.js`
- `client/src/views/ModelTraining.js`
- `client/src/views/RunModel.js`
- `client/src/views/ProjectProgress.js`
- `client/src/views/Proofread.js`
- `client/src/views/Views.js`

Local docs to inspect if uploaded or accessible:

- `docs/research/agentic-workflow-formalization-report.md`
- `docs/research/deep-research-agentic-bioimage-segmentation.md`
- `docs/research/deep-research-engineering-synthesis-2026-05-24.md`
- `docs/research/internal-technical-audit-2026-05-24.md`
- `docs/research/claude-code-agent-patterns.md`
- `docs/codex-working-memory/progress-log.md`
- `docs/codex-working-memory/backlog.md`
- `docs/codex-working-memory/paper-readiness-production-plan.md`

## Existing Report Claims To Audit

Audit these claims carefully:

1. The system should be framed as a **mixed-initiative workflow agent for iterative biomedical image segmentation**.
2. Product term should be **Workflow Assistant** or **Segmentation Workflow Assistant**.
3. The central abstraction should be **project memory plus action proposals**, not chat history.
4. Project memory should cover:
   - project facts;
   - task-family preset;
   - per-volume state;
   - artifact index;
   - run history;
   - proofreading/edit history;
   - evaluation history;
   - user confirmations;
   - evidence events;
   - freshness/invalidation markers.
5. Actions should be typed and bounded:
   - read-only actions;
   - navigation actions;
   - form-populating actions;
   - approval-gated runtime actions;
   - mutating project-state actions;
   - expensive training/inference actions;
   - refusals/blockers.
6. Per-volume states should include:
   - `image_only`
   - `draft_segmentation`
   - `needs_proofreading`
   - `proofread_ground_truth`
   - `training_candidate`
   - `queued_for_inference`
   - `prediction_ready`
   - `ignored`
7. The strongest third case may be CREMI-style affinity-heavy connectomics, but this must be challenged against Lucchi++ and SNEMI3D.
8. The defensible paper claim is workflow coordination/provenance, not accuracy improvement.

## Research Questions

Answer in concrete, implementation-oriented terms.

1. What is the right formal model for the agent?
   - workflow orchestration agent;
   - mixed-initiative assistant;
   - scientific workflow manager;
   - interactive ML collaborator;
   - or another framing?
   - What should the paper call it?
   - What should the product call it?

2. What is the right project-memory schema?
   - required dataset-level facts;
   - per-volume state;
   - artifact index;
   - run history;
   - proofreading/edit history;
   - evidence/provenance ledger;
   - user/context confirmations;
   - invalidation or refresh timestamps.

3. What should the agent be allowed to inspect?
   - mounted filesystem tree;
   - `project_manifest.json`;
   - PyTC configs;
   - volume dimensions/dtypes/metadata;
   - labels/predictions/checkpoints;
   - progress statuses;
   - workflow events;
   - logs and metrics;
   - proofreading edits;
   - screenshots or viewer-derived observations if feasible.

4. When should the agent re-inspect instead of trusting cached memory?
   - file watcher events;
   - user status changes;
   - workflow stage changes;
   - training/inference job lifecycle;
   - proofread edit saves;
   - app resume after idle;
   - user asks freshness-sensitive questions.

5. What should the action model look like?
   - card schema;
   - required fields;
   - approval behavior;
   - execution routing;
   - result/provenance logging;
   - refusal/blocker behavior.

6. What makes an action proposal understandable to biologists?
   - minimal training card fields;
   - minimal inference card fields;
   - proofreading queue fields;
   - status-change fields;
   - affected-volume presentation;
   - progressive disclosure.

7. How should context elicitation work?
   - first-run flow after mounting a project;
   - auto-detected facts;
   - checkable/editable suggestions;
   - short questions;
   - "I don't know" options;
   - voice-friendly prompts;
   - correction persistence.

8. What should "Codex/Claude Code for segmentation workflows" mean?
   - which coding-agent patterns transfer;
   - which do not transfer;
   - how to show plans, traces, approvals, interruption, resume, and recoverability.

9. What safety and provenance guarantees are necessary?
   - human approval;
   - reproducible configs;
   - run manifests;
   - undo/versioning;
   - evidence trail;
   - no hidden arbitrary shell execution.

10. How should the system be evaluated for a paper?

- defensible claims;
- participant tasks;
- baselines;
- metrics;
- qualitative evidence;
- claims to avoid.

## Literature And Systems Areas To Review

Use current web search and prefer primary sources where possible. Include links/citations.

### Human-Agent And Mixed-Initiative Interaction

Review:

- Eric Horvitz, "Principles of Mixed-Initiative User Interfaces";
- Saleema Amershi et al., "Guidelines for Human-AI Interaction";
- Amershi et al., "The Role of Humans in Interactive Machine Learning";
- intent elicitation in mixed-initiative systems;
- progressive disclosure;
- explanation for correction, not raw chain-of-thought;
- approval-gated autonomy;
- recoverability and user control.

### Agentic Developer Tools

Review product/system patterns from:

- OpenAI Codex;
- Claude Code;
- GitHub Copilot agent mode / coding agent;
- Cursor / Windsurf-style coding agents.

Treat these as design-pattern references, not scientific proof. Focus on:

- inspect-plan-act loops;
- tool calling;
- approval gates;
- reviewable diffs or reviewable action artifacts;
- long-running task progress;
- traces/logs;
- context compaction and memory;
- project understanding;
- bounded execution environments;
- user interruption and resume.

### Bioimage Workflow Tools

Review:

- ilastik;
- CellProfiler;
- Fiji/ImageJ;
- napari;
- napari-imagej;
- Neuroglancer;
- WEBKNOSSOS;
- VAST;
- BigDataViewer;
- MoBIE;
- OMERO;
- OME-Zarr;
- REMBI.

Focus on:

- guided setup;
- workflow recipes;
- project metadata;
- annotation/proofreading state;
- volume visualization;
- collaboration;
- reproducibility;
- non-programmer usability.

### Connectomics And Segmentation Infrastructure

Review:

- PyTorch Connectomics tutorials/configs;
- MitoEM and MitoEM2.0;
- Lucchi++;
- SNEMI3D;
- CREMI;
- CAVE / Connectome Annotation Versioning Engine;
- proofreading and versioned annotation systems.

Focus on:

- data representations;
- semantic masks vs instance labels vs affinities;
- train/infer/evaluate loops;
- proofreading loops;
- valid masks / partially annotated supervision;
- provenance and reproducibility.

### Scientific Workflow And Provenance

Review:

- W3C PROV;
- scientific workflow provenance;
- experiment tracking;
- MLflow / DVC-style lineage;
- reproducible computational pipelines;
- workflow provenance in image analysis;
- human-in-the-loop ML experiment management.

The key question: what is the **minimum provenance model** this product needs to be credible in a biomedical setting?

## Required Report Sections

### 1. Executive Summary

One to two pages max. State the recommended agent architecture and why.

### 2. Current Prototype Diagnosis

Ground this in public code or provided excerpts. Explicitly mark anything needing local verification.

Cover:

- what exists now;
- where the agent is strong;
- where implementation is brittle;
- where state is duplicated or stale;
- where UI/action semantics are unclear;
- what should be fixed first.

### 3. Literature-Backed Design Principles

Use a table:

| Principle | Evidence | App Implication | Priority |
| --------- | -------- | --------------- | -------- |

Each row must cite real papers/docs/systems.

### 4. Proposed Agent Architecture

Include a Mermaid diagram.

Specify:

- project inspector;
- normalized project memory;
- retrieval/context layer;
- assistant response layer;
- trace/evidence layer;
- action proposal generator;
- approval policy;
- bounded workflow executor;
- artifact/provenance ledger;
- invalidation/reinspection loop.

### 5. Project Memory Schema

Provide JSON-like schema covering:

- dataset/project facts;
- task-family preset;
- volume states;
- artifact index;
- run history;
- proofreading/edit history;
- metrics/evaluation history;
- user confirmations;
- evidence events;
- stale/freshness markers.

### 6. Volume And Workflow State Machine

Define volume states and transitions.

Minimum states:

- `image_only`
- `draft_segmentation`
- `needs_proofreading`
- `proofread_ground_truth`
- `training_candidate`
- `queued_for_inference`
- `prediction_ready`
- `ignored`

Include:

- actor allowed to transition;
- evidence required;
- approval requirement;
- representation of partial or region-level proofreading.

### 7. Action Card Specification

Define card types, required fields, and approval behavior for:

- visualize data;
- choose/change data;
- open progress;
- start training;
- start inference;
- queue proofreading;
- mark volume status;
- export corrected masks;
- evaluate/compare results;
- export evidence bundle.

Specify:

- plain-language summary;
- affected volumes;
- inputs;
- outputs;
- risks/costs;
- expected duration if knowable;
- review details;
- approval/reject behavior;
- resulting events.

### 8. Guided Context Elicitation

Design first-run flow after mounting a project.

Avoid blank boxes by using:

- auto-detected facts;
- checkable/editable suggestions;
- concrete short questions;
- examples;
- "I don't know" options;
- voice-friendly prompts if applicable.

Specify questions for:

- mitochondria semantic segmentation;
- mitochondria instance segmentation;
- XRI fibre / TapeReader;
- affinity-heavy neuron segmentation;
- synapse/cleft segmentation.

### 9. Case Study-Specific Requirements

For each case:

- expected files;
- expected labels;
- expected configs;
- workflow loop;
- progress states;
- what the agent should know;
- what the agent should not assume;
- demo tasks;
- paper evidence it can generate.

Include a clear recommendation for the third case study and alternatives considered.

### 10. Evaluation Plan For The Paper

Include:

- participant profile;
- tasks;
- conditions or baselines;
- data to log;
- interview prompts;
- success criteria;
- risks to claims;
- defensible claims;
- claims to avoid.

### 11. Engineering Roadmap

Prioritize into:

- immediate fixes for current prototype;
- paper-demo requirements;
- production-quality requirements;
- future/research extensions.

Each item should include:

- user value;
- affected code areas;
- required backend changes;
- required frontend changes;
- test/verification plan;
- paper relevance.

### 12. Open Questions

List unresolved questions requiring team decisions, not just engineering execution.

## Quality Bar

A good report will:

- cite specific papers, systems, and documentation;
- distinguish verified facts from assumptions;
- inspect public/local code where possible;
- name concrete implementation gaps;
- propose a project-memory schema detailed enough to implement;
- propose action-card behavior detailed enough for UI implementation;
- explain how the design supports a systems/HCI paper;
- identify what evidence the app should log;
- warn clearly about overclaims.

A bad report will:

- say "use RAG" without specifying what is retrieved and when;
- say "make the agent autonomous" without approval boundaries;
- propose arbitrary shell execution as the core agent model;
- ignore project progress and per-volume state;
- ignore biological onboarding;
- ignore provenance and reproducibility;
- treat all segmentation workflows as generic binary masks;
- recommend showing hidden chain-of-thought as the transparency mechanism;
- claim local code inspection when it did not happen.

## Final Recommendation Shape

End with a concise recommendation like:

> Build the assistant as a workflow-aware, approval-gated project operator. The central abstraction is not chat history; it is project memory plus action proposals. Chat is the conversational surface. Project memory is the source of truth. Action cards are the bridge from intent to bounded execution. Evidence events are the paper-grade provenance layer.

The exact wording can change, but the final answer should make the architecture and product direction this concrete.
