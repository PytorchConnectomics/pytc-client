# Deep Research Task: Formalizing The Agentic Segmentation Workflow

## Purpose

Investigate how the seg.bio / PyTC Client assistant should evolve from a useful prototype into a rigorous workflow-aware agent for biomedical image segmentation.

The research target is not "add a chatbot." The target is a system closer to Codex or Claude Code, but specialized for volumetric biomedical segmentation: it should inspect a mounted project, maintain grounded project memory, propose bounded app actions, ask concrete context questions when needed, execute approved routines, and keep the user oriented across visualization, proofreading, training, inference, and evaluation.

The output should give the engineering team a concrete architecture, implementation roadmap, and literature-backed design rationale for improving the current agentic implementation.

## Local Project Context

Primary working checkout on this machine:

- `/home/weidf/deploy/pytc-client-demo2`

Public/demo deployment:

- `https://demo.seg.bio`

Primary repositories:

- PyTC Client / seg.bio app: `https://github.com/PytorchConnectomics/pytc-client`
- PyTorch Connectomics backend library: `https://github.com/PytorchConnectomics/pytorch_connectomics`
- TapeReader reference pipeline for the Yixiao/XRI case study: `https://github.com/LinghuLab/TapeReader`

The current prototype includes:

- `Files`: mount and inspect project folders.
- `Visualize`: open image/mask volumes in Neuroglancer.
- `Train Model`: configure and launch PyTorch Connectomics training.
- `Run Model`: configure and launch inference.
- `Progress`: volume-level workflow tracking.
- `Proofread`: review and correct segmentation masks.
- `Assistant`: workflow-aware chat plus action cards.

The `Monitor` tab has been intentionally sunset. Runtime status should live near the relevant action surface: training state in Train Model, inference state in Run Model, proofreading state in Proofread, and project state in Progress / workflow overview.

## Current Case Studies

Treat these as the three paper/prototype cases. Fill in missing details as you inspect local folders and repo docs.

### Case Study 1: MitoEM / MitoEM2-Style Progress Workflow

Likely local fixture:

- `/home/weidf/demo_data/mitoem2_progress_demo`

Core workflow:

- EM/ssSEM mitochondria instance segmentation.
- Some volumes are confirmed ground truth.
- Some volumes have draft segmentations needing proofreading.
- Some volumes are image-only targets.
- The agent should train from confirmed/proofread ground truth and propose inference for image-only volumes.

### Case Study 2: Yixiao / TapeReader XRI Fibre Workflow

Current local fixture:

- `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`

Reference project:

- TapeReader pipeline: `https://github.com/LinghuLab/TapeReader`
- Paper: `https://www.biorxiv.org/content/10.1101/2025.05.10.653182v1`

Current split:

- 10 tracked XRI volumes.
- 6 confirmed ground-truth masks.
- 2 draft masks needing proofreading.
- 2 image-only inference targets.
- Active voxel spacing: `40 x 16.3 x 16.3 nm` in z,y,x.
- Active app-compatible config: `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`.

Core workflow:

- XRI/CytoTape fibre instance segmentation.
- Use confirmed masks for training.
- Use draft masks for proofreading and later promotion.
- Use image-only volumes as inference targets.
- Preserve the distinction between paper-faithful TapeReader config semantics and current app-compatible PyTC fallback config semantics.

### Case Study 3: Placeholder

Identify what the third case should be and what agentic capabilities it should stress.

Candidate families:

- Lucchi++ for reliable onboarding/demo.
- SNEMI3D or CREMI for affinity-heavy connectomics.
- NucMM or another non-mitochondria volumetric segmentation workflow.

The research output should recommend the strongest third case for the paper and explain which agent/workflow behaviors it exercises.

## Current Engineering Problem

The assistant has improved, but the agentic architecture is still not formal enough.

Known pain points:

- The agent sometimes answers from stale or incomplete project context.
- Project context is assembled from multiple places: scanned files, manifests, workflow state, progress state, user chat, and runtime events.
- There is not yet one canonical project-memory contract that all app modules and the agent treat as the shared source of truth.
- Action cards exist, but the policy for when to propose, ask, approve, execute, or refuse needs to be formalized.
- The initial setup experience can still strand biologists in blank text boxes instead of guiding them through concrete project facts.
- The agent should be able to inspect project state and ask targeted questions, but it should not pretend to see or validate things it cannot actually inspect.
- The visible chat voice should feel like a normal helpful assistant, while inspection details should be available through progressive disclosure.
- Training/inference/proofreading actions should be bounded app routines, not arbitrary shell execution.
- Long-running jobs and artifact mutations need durable provenance.
- The paper needs a defensible explanation of why this is a coherent human-agent workflow system, not just a UI wrapped around an LLM.

## Research Questions

Answer these in concrete, implementation-oriented terms.

1. What is the right formal model for the agent?
   - Should it be framed as a workflow orchestration agent, mixed-initiative assistant, scientific workflow manager, interactive ML collaborator, or something else?
   - What should the paper call it?
   - What should the product call it?

2. What is the right project-memory schema?
   - Required dataset-level facts.
   - Required per-volume state.
   - Required artifact index.
   - Required run history.
   - Required proofreading/edit history.
   - Required evidence/provenance ledger.
   - Required user/context confirmations.
   - Required invalidation or refresh timestamps.

3. What should the agent be allowed to inspect?
   - Mounted filesystem tree.
   - `project_manifest.json`.
   - PyTC configs.
   - volume dimensions/dtypes/metadata.
   - available labels/predictions/checkpoints.
   - progress statuses.
   - workflow events.
   - logs and metrics.
   - proofreading edits.
   - screenshots or viewer-derived observations, if feasible.

4. When should the agent re-inspect instead of trusting cached memory?
   - File watcher events.
   - user changes status.
   - workflow changes stage.
   - training/inference job starts/completes/fails.
   - edits are saved.
   - app resumes from idle.
   - user asks a question requiring fresh state.

5. What should the action model look like?
   - Read-only actions.
   - Navigation actions.
   - Form-populating actions.
   - Approval-gated runtime actions.
   - Mutating project-state actions.
   - Expensive training/inference actions.
   - Refusals/blockers when preconditions are missing.

6. What makes an action proposal understandable to biologists?
   - Minimal fields for a training card.
   - Minimal fields for an inference card.
   - Minimal fields for proofreading queue actions.
   - Minimal fields for status changes.
   - How to show affected volumes without dumping huge JSON.
   - How to expose details only when the user wants them.

7. How should context elicitation work?
   - What questions should the app ask after mounting a project?
   - How can auto-detected facts reduce blank-page anxiety?
   - How should voice/speech input fit?
   - How should the user correct wrong guesses?
   - How should corrections persist back into project memory?

8. What should "Codex/Claude Code for segmentation workflows" mean here?
   - Which coding-agent patterns transfer cleanly?
   - Which patterns do not transfer because biomedical workflows involve data, compute, provenance, and scientific interpretation?
   - How should the product show plans, traces, approvals, and recoverability?

9. What safety and provenance guarantees are necessary?
   - Human approval for expensive/mutating actions.
   - Reproducible configs and run manifests.
   - Undo/versioning for project status changes.
   - Evidence trail for why the agent made a suggestion.
   - Avoiding hidden arbitrary shell execution.

10. How should the system be evaluated for a paper?

- What claims are defensible?
- What study tasks should participants perform?
- What metrics or qualitative evidence would show that the agent improves coordination?
- What claims should be avoided unless there is stronger evidence?

## Code Areas To Inspect

Start with these files and neighboring modules. Names may drift; use `rg` if needed.

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
- `client/src/contexts/WorkflowContext.js`
- `client/src/contexts/GlobalContext.js`
- `client/src/views/FilesManager.js`
- `client/src/views/Visualization.js`
- `client/src/views/ModelTraining.js`
- `client/src/views/RunModel.js`
- `client/src/views/ProjectProgress.js`
- `client/src/views/Proofread.js`
- `client/src/views/Views.js`

Project docs:

- `docs/codex-working-memory/progress-log.md`
- `docs/codex-working-memory/backlog.md`
- `docs/codex-working-memory/paper-readiness-production-plan.md`
- `docs/research/deep-research-agentic-bioimage-segmentation.md`
- `docs/research/deep-research-engineering-synthesis-2026-05-24.md`
- `docs/research/internal-technical-audit-2026-05-24.md`
- `docs/research/claude-code-agent-patterns.md`

Local data fixtures:

- `/home/weidf/demo_data/mitoem2_progress_demo`
- `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`
- `/home/weidf/demo_data/yixiao_tapereader_xri_case_study_holdout_masks`

## Literature And Systems Areas To Review

Use current web search and primary sources where possible. The output must include links/citations.

### Human-Agent And Mixed-Initiative Interaction

Look for work on:

- mixed-initiative user interfaces;
- interactive machine learning;
- human-AI interaction guidelines;
- intent elicitation;
- progressive disclosure;
- explanation as support for correction, not raw chain-of-thought dumping;
- approval-gated autonomy;
- recoverability and user control.

Seed references and keywords:

- Eric Horvitz, "Principles of Mixed-Initiative User Interfaces"
- Saleema Amershi et al., "Guidelines for Human-AI Interaction"
- Amershi et al., "The Role of Humans in Interactive Machine Learning"
- intent elicitation in mixed-initiative systems
- domain knowledge elicitation in applied ML
- human-centered AI workflow systems

### Agentic Developer Tools

Review product/system patterns from:

- Codex
- Claude Code
- GitHub Copilot agent mode
- Cursor / Windsurf-style coding agents
- any recent papers or docs on agentic coding tools

Do not treat these as scientific proof. Treat them as design-pattern references.

Pay attention to:

- inspect-plan-act loops;
- tool calling;
- approval gates;
- diffs and patches as reviewable artifacts;
- long-running task progress;
- traces/logs;
- context compaction and memory;
- filesystem/project understanding;
- bounded execution environments;
- user interruption and resume behavior.

### Bioimage Workflow Tools

Review tools that biologists actually use:

- ilastik
- CellProfiler
- Fiji/ImageJ
- napari
- napari-imagej
- Neuroglancer
- WEBKNOSSOS
- VAST
- BigDataViewer
- MoBIE
- OMERO
- OME-Zarr / REMBI

Focus on what they teach about:

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

Review systems/literature around:

- scientific workflow management;
- provenance graphs;
- experiment tracking;
- reproducible computational pipelines;
- workflow provenance in image analysis;
- human-in-the-loop ML experiment management.

The question: what is the minimum provenance model this product needs to be credible in a biomedical setting?

## Expected Output

Write the final research report as a markdown file in:

- `docs/research/agentic-workflow-formalization-report.md`

The report should include these sections.

### 1. Executive Summary

One to two pages max. State the recommended agent architecture and why.

### 2. Current Prototype Diagnosis

Grounded in code inspection:

- what exists now;
- where the agent is already strong;
- where the current implementation is brittle;
- where state is duplicated or stale;
- where UI/action semantics are unclear;
- what should be fixed first.

### 3. Literature-Backed Design Principles

For each principle:

- cite the relevant literature/systems;
- state the design implication;
- map it to this app.

Example format:

| Principle                                       | Evidence | App Implication              | Priority |
| ----------------------------------------------- | -------- | ---------------------------- | -------- |
| Ask concrete questions instead of blank prompts | ...      | Guided project intake wizard | High     |

### 4. Proposed Agent Architecture

Include a diagram, preferably Mermaid.

At minimum, specify:

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

Propose a concrete schema in JSON-like form.

It should cover:

- dataset/project facts;
- task family preset;
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

- who/what can transition each state;
- what evidence is required;
- which transitions require approval;
- how partial or region-level proofreading should be represented.

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
- evaluate/compare results.

Specify:

- plain-language summary;
- affected volumes;
- inputs;
- outputs;
- risks/costs;
- expected duration if knowable;
- review details;
- approval/reject behavior;
- how resulting events are written.

### 8. Guided Context Elicitation

Design the first-run flow after mounting a project.

It should avoid blank boxes by using:

- auto-detected facts;
- checkable/editable suggestions;
- concrete short questions;
- examples;
- "I don't know" options;
- voice-friendly prompts if applicable.

Specify what the app should ask for each workflow family:

- mitochondria semantic segmentation;
- mitochondria instance segmentation;
- XRI fibre / TapeReader;
- affinity-heavy neuron segmentation;
- synapse/cleft segmentation.

### 9. Case Study-Specific Requirements

For each case study:

- expected files;
- expected labels;
- expected configs;
- workflow loop;
- progress states;
- what the agent should know;
- what the agent should not assume;
- demo tasks;
- paper evidence it can generate.

Include concrete recommendations for the third case study.

### 10. Evaluation Plan For The Paper

Propose a realistic study plan.

Include:

- participant profile;
- tasks;
- conditions or comparison baselines;
- data to log;
- interview prompts;
- success criteria;
- risks to claims;
- defensible claims;
- claims to avoid.

### 11. Engineering Roadmap

Prioritize implementation into:

- immediate fixes for the current prototype;
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

List unresolved questions that require user/team decisions, not just engineering execution.

## Quality Bar

The final report must be actionable. It should not be a generic LLM-agent essay.

A good report will:

- cite specific papers, systems, and documentation;
- inspect the actual codebase and name concrete implementation gaps;
- distinguish established design patterns from speculative ideas;
- propose a schema detailed enough for engineers to implement;
- propose action-card behavior detailed enough for UI implementation;
- explain how the design supports a TOCHI-style systems/HCI paper;
- identify what evidence the app should log to support the paper;
- warn clearly about overclaims.

A bad report will:

- say "use RAG" without specifying what gets retrieved and when;
- say "make the agent more autonomous" without approval boundaries;
- propose arbitrary shell execution as the core agent model;
- ignore project progress and per-volume state;
- ignore biological user onboarding;
- ignore provenance and reproducibility;
- treat all segmentation workflows as generic binary masks;
- recommend showing hidden chain-of-thought as the main transparency mechanism.

## Suggested Final Recommendation Shape

The report should end with a concise recommendation like:

> Build the assistant as a workflow-aware, approval-gated project operator. The central abstraction is not chat history; it is project memory plus action proposals. Chat is the conversational surface. Project memory is the source of truth. Action cards are the bridge from intent to bounded execution. Evidence events are the paper-grade provenance layer.

The exact wording can change, but the final answer should make the architecture and product direction this concrete.
