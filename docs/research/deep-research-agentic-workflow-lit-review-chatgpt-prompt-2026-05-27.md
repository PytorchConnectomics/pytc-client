# ChatGPT Deep Research Task: Literature Review For A Workflow-Aware Biomedical Segmentation Agent

## Role

Act as an external HCI / human-agent interaction / scientific workflow research agent.

Your job is to perform a **current literature and systems review** and synthesize concrete design improvements for an existing prototype: a workflow-aware assistant for biomedical volume segmentation in seg.bio / PyTC Client.

You are **not** expected to access the local prototype, local filesystem, or private development state. You should not claim to inspect code unless code is explicitly uploaded or pasted. This task is primarily a literature review and design synthesis task.

## Core Question

How should a biomedical image-segmentation assistant evolve from a useful chat/action prototype into a rigorous, workflow-aware, mixed-initiative agent?

The target is not "add a chatbot." The target is closer to Codex / Claude Code in workflow discipline, but specialized for volumetric biomedical segmentation: it should inspect a mounted project, maintain grounded project memory, propose bounded app actions, ask concrete context questions, execute approved app routines, and keep the user oriented across visualization, proofreading, training, inference, evaluation, and evidence export.

## Important Constraints

- Do **not** assume access to the local repository or machine.
- Do **not** over-index on implementation details unless they are included below.
- Do **not** recommend arbitrary shell execution as the agent model.
- Do **not** recommend exposing hidden chain-of-thought as the transparency mechanism.
- Do **not** make unsupported claims that the assistant improves segmentation accuracy.
- Focus on HCI, human-agent collaboration, interactive ML, scientific workflow/provenance, and bioimage-analysis workflow systems.

## Prototype Context You Should Assume

The prototype is a web app for biomedical image segmentation workflows. It is public-facing as:

- https://demo.seg.bio

Most up-to-date code context, if web-accessible:

- Repository: https://github.com/PytorchConnectomics/pytc-client
- Target branch: `checkpoint/tochi-agentic-prototype`
- Branch URL: https://github.com/PytorchConnectomics/pytc-client/tree/checkpoint/tochi-agentic-prototype

If this branch is unavailable or not fully accessible from your environment, do **not** infer code details from the default branch alone. Use the prototype context in this prompt as the authoritative current-state description, and cite public/default-branch code only as broader context with a note that it may lag the prototype.

The app is built around PyTC Client / seg.bio and PyTorch Connectomics concepts, but you should treat this prompt as the source of truth if you cannot inspect the code.

### Current Product Modules

The app has these workflow surfaces:

- **Files:** mount and inspect project folders.
- **Visualize:** open image/mask volumes in Neuroglancer.
- **Train Model:** configure and launch PyTorch Connectomics training.
- **Run Model:** configure and launch inference.
- **Progress:** track volume-level workflow status.
- **Proofread:** review and correct segmentation masks.
- **Assistant:** workflow-aware chat with action cards.

The old `Monitor` tab has been intentionally sunset. Runtime status should live near the action surface:

- training state in Train Model;
- inference state in Run Model;
- proofreading state in Proofread;
- project state in Progress / workflow overview.

### Current Assistant Behavior

The assistant currently:

- answers workflow questions in chat;
- can suggest app actions such as opening a view, choosing data, training, inference, proofreading, evaluation, or evidence export;
- shows action cards;
- has approval gates for consequential actions;
- can maintain some workflow events, artifacts, model runs, correction sets, evaluations, and volume states;
- can scan mounted folders and infer file roles;
- can read project manifests if present;
- can derive volume-level progress for demo fixtures;
- can export evidence bundles containing workflow events and artifacts.

### Current Pain Points

The architecture is useful but not yet formal enough:

- The assistant can answer from stale or incomplete project context.
- Project context is assembled from several places: scanned files, manifests, workflow state, progress state, user chat, and runtime events.
- There is no single canonical project-memory contract shared by all app modules and the assistant.
- Action cards exist, but policy for when to propose, ask, approve, execute, or refuse needs stronger formalization.
- Initial setup can strand biologists in blank text boxes instead of guiding them through concrete detected project facts.
- The assistant should inspect project state and ask targeted questions, but should not pretend to validate facts it cannot inspect.
- Visible chat should feel like a normal helpful assistant; inspection details should be available through progressive disclosure.
- Training, inference, and proofreading actions should be bounded app routines, not arbitrary shell execution.
- Long-running jobs and artifact mutations need durable provenance.
- The paper needs a defensible explanation of why this is a coherent human-agent workflow system, not just a UI wrapped around an LLM.

## Proposed Direction To Critique And Improve

The current internal recommendation is:

> Build the assistant as a workflow-aware, approval-gated project operator. The central abstraction is not chat history; it is project memory plus action proposals. Chat is the conversational surface. Project memory is the source of truth. Action cards are the bridge from intent to bounded execution. Evidence events are the paper-grade provenance layer.

Please critique, validate, and improve this recommendation using literature and systems evidence.

### Candidate Framing

Possible paper framing:

- **mixed-initiative workflow agent for iterative biomedical image segmentation**

Possible product framing:

- **Workflow Assistant**
- **Segmentation Workflow Assistant**

Please evaluate whether this is the strongest framing. Compare against:

- workflow orchestration agent;
- mixed-initiative assistant;
- scientific workflow manager;
- interactive ML collaborator;
- human-AI workflow coordinator;
- AI copilot for bioimage segmentation;
- agentic project operator.

## Candidate Architecture To Evaluate

Assume the app could be restructured around:

1. **Project inspector**
   - Reads mounted filesystem tree, project manifest, configs, image metadata, label/prediction/checkpoint availability, logs, metrics, and proofreading exports.

2. **Canonical project memory**
   - Shared state model for project facts, per-volume status, artifacts, runs, proofreading history, evaluations, user confirmations, evidence events, and freshness markers.

3. **Context/retrieval layer**
   - Builds concise, current assistant context from project memory and re-inspects when needed.

4. **Assistant response layer**
   - Produces short, normal, biologist-facing chat responses.

5. **Trace/evidence layer**
   - Provides expandable details: what was inspected, when, which files or statuses supported the answer, and uncertainty.

6. **Action proposal generator**
   - Creates typed cards for bounded app actions.

7. **Approval policy**
   - Lets read-only/navigation/form-prefill actions run with low friction; requires human approval for mutating, expensive, runtime, editor-launching, status-changing, or export actions.

8. **Bounded workflow executor**
   - Executes only app-defined routines: mount project, open viewer, prefill training/inference forms, launch training/inference, queue proofreading, mark status, export masks, compute metrics, export evidence.

9. **Artifact/provenance ledger**
   - Records observations, user confirmations, proposals, approvals/rejections, executions, artifacts, volume transitions, job statuses, metrics, and exported evidence.

10. **Invalidation/reinspection loop**

- Refreshes memory when files change, statuses change, jobs start/complete/fail, proofread edits are saved, app resumes, or a user asks a freshness-sensitive question.

Please assess this architecture against HCI/agent/workflow/provenance literature.

## Candidate Project Memory Schema To Evaluate

Assume the project memory should include:

- dataset/project facts:
  - title;
  - project roots;
  - imaging modality;
  - target structure;
  - voxel size;
  - axes;
  - dtype;
  - label semantics;
  - task family;
  - source and confirmation status for each fact.
- task-family preset:
  - expected inputs;
  - expected outputs;
  - model/config family;
  - proofreading expectations;
  - evaluation metrics;
  - safe defaults.
- per-volume state:
  - volume id/name;
  - image path;
  - label path;
  - prediction path;
  - corrected mask path;
  - state;
  - state source;
  - confidence;
  - training/inference eligibility;
  - shape/dtype/stats;
  - partial-region status if relevant.
- artifact index:
  - configs;
  - raw images;
  - masks;
  - predictions;
  - checkpoints;
  - logs;
  - metrics;
  - evidence bundles;
  - checksums if feasible.
- run history:
  - training, inference, evaluation, proofreading sessions;
  - inputs;
  - outputs;
  - configs;
  - status;
  - timestamps;
  - metrics.
- proofreading/edit history:
  - source mask;
  - corrected mask;
  - edited regions/instances where feasible;
  - reviewer;
  - promotion decision.
- user confirmations:
  - facts corrected by user;
  - trusted masks;
  - training policy;
  - task-family choice.
- evidence events:
  - observations;
  - proposals;
  - approvals/rejections;
  - actions;
  - status transitions;
  - artifacts created;
  - errors.
- freshness/invalidation markers:
  - last scanned;
  - invalidated by;
  - stale domains;
  - reinspection need.

Please improve this schema from the literature. Identify missing fields, unnecessary fields, and how to keep it minimal but credible.

## Candidate Volume States To Evaluate

Internal recommendation:

- `image_only`
- `draft_segmentation`
- `needs_proofreading`
- `proofread_ground_truth`
- `training_candidate`
- `queued_for_inference`
- `prediction_ready`
- `ignored`

Please evaluate whether these states are adequate for:

- mitochondria semantic segmentation;
- mitochondria instance segmentation;
- XRI fibre instance segmentation;
- affinity-heavy neuron segmentation;
- synapse/cleft segmentation;
- partial or region-level proofreading.

Suggest state names, transitions, evidence requirements, and approval requirements.

## Case Study Context

### Case Study 1: MitoEM / MitoEM2-Style Progress Workflow

Assume a demo fixture modeled on MitoEM/MitoEM2:

- EM/ssSEM mitochondria instance segmentation.
- 6 small HDF5 smoke volumes.
- Initial split:
  - 2 confirmed/proofread ground truth;
  - 2 draft segmentations needing proofreading;
  - 2 image-only targets.
- Voxel size: z,y,x = 30,8,8 nm.
- Core workflow:
  - train from confirmed/proofread ground truth;
  - proofread draft masks;
  - run inference on image-only volumes;
  - evaluate with withheld ground truth where available.

What the assistant should know:

- not all masks are safe for training;
- ground truth and draft segmentations are different states;
- image-only targets should not be treated as labeled data;
- MitoEM/MitoEM2 are about challenging 3D mitochondria instance segmentation, not just binary masks.

### Case Study 2: Yixiao / TapeReader XRI Fibre Workflow

Assume a demo fixture modeled on a TapeReader XRI fibre workflow:

- 10 tracked XRI volumes.
- 6 confirmed ground-truth masks: `1`, `2`, `3`, `4_1`, `4_2`, `4_3`.
- 2 draft masks needing proofreading: `5_1`, `5_2`.
- 2 image-only inference targets: `6_1`, `6_2`.
- Voxel spacing: z,y,x = 40,16.3,16.3 nm.
- Active app-compatible config: `configs/TapeReader-Fiber-BCS-AppCompat-Sanity.yaml`.
- Paper-faithful config: `configs/TapeReader-Fiber-BCS-Original-Barcode.yaml`.
- Reference project: https://github.com/LinghuLab/TapeReader
- Paper/preprint: https://www.biorxiv.org/content/10.1101/2025.05.10.653182v1

Core workflow:

- XRI/CytoTape fibre instance segmentation.
- Use confirmed masks for training.
- Use draft masks for proofreading and later promotion.
- Use image-only volumes as inference targets.
- Preserve distinction between paper-faithful TapeReader config semantics and app-compatible PyTC fallback semantics.

What the assistant should know:

- training set is not "all masks in folder";
- proofread status controls training eligibility;
- image-only volumes are inference targets;
- app-compatible config may be a practical fallback, not a reproduction of the paper.

### Case Study 3: To Recommend

Recommend the strongest third case study.

Candidates:

- **Lucchi++**:
  - reliable onboarding/demo;
  - mitochondria semantic/instance segmentation;
  - easier for users;
  - may overlap with MitoEM.
- **SNEMI3D or CREMI**:
  - affinity-heavy connectomics;
  - stresses valid masks, partial labels, split/merge proofreading, topology-aware evaluation;
  - likely harder to implement/demo.
- **NucMM / Nuc3D / other non-mitochondria volumetric segmentation**:
  - broadens biological scope;
  - may stress nuclei instance labels rather than connectomics affinities.

Please recommend the strongest third case for:

- a paper prototype;
- a reliable public demo;
- long-term research value.

These may be different recommendations.

## Literature Areas To Review

Use current web search and cite primary sources where possible.

### 1. Human-Agent And Mixed-Initiative Interaction

Review and synthesize:

- mixed-initiative user interfaces;
- intent elicitation;
- user control and recoverability;
- approval-gated autonomy;
- progressive disclosure;
- explanation as support for correction, not chain-of-thought dumping;
- human-AI interaction guidelines.

Seed references:

- Eric Horvitz, "Principles of Mixed-Initiative User Interfaces";
- Saleema Amershi et al., "Guidelines for Human-AI Interaction";
- Amershi et al., "The Role of Humans in Interactive Machine Learning";
- recent HCI work on human-agent collaboration, AI copilots, or workflow agents.

### 2. Agentic AI / Developer Agent Systems

Review design patterns from:

- OpenAI Codex;
- Claude Code;
- GitHub Copilot agent mode / coding agent;
- Cursor / Windsurf-like agents;
- recent papers or technical reports on agentic coding tools;
- tool-calling agent architectures.

Treat these as systems/design references rather than scientific proof.

Focus on:

- inspect-plan-act loops;
- tool calling;
- approval gates;
- reviewable artifacts;
- long-running task progress;
- traces/logs;
- memory/context management;
- project understanding;
- bounded execution;
- interruption/resume;
- permission models.

Translate carefully to biomedical workflows. Explain what transfers and what does not.

### 3. Interactive Machine Learning And Human-In-The-Loop ML

Review:

- interactive ML;
- active learning interfaces;
- human correction loops;
- human control over training data;
- model update provenance;
- error correction and trust calibration.

Map to:

- proofread masks;
- promote corrected masks to ground truth;
- train from confirmed data;
- infer image-only volumes;
- evaluate before/after results.

### 4. Bioimage Workflow Tools

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

Focus on lessons for:

- guided setup;
- non-programmer usability;
- workflow recipes;
- metadata;
- project/session state;
- annotation/proofreading;
- volume visualization;
- collaboration;
- reproducibility.

### 5. Connectomics And Segmentation Infrastructure

Review:

- PyTorch Connectomics;
- MitoEM;
- MitoEM2.0;
- Lucchi++;
- SNEMI3D;
- CREMI;
- CAVE / Connectome Annotation Versioning Engine;
- proofreading/versioned annotation systems.

Focus on:

- semantic masks vs instance labels vs affinities;
- train/infer/evaluate loops;
- proofreading loops;
- valid masks and partial annotation;
- segmentation provenance.

### 6. Scientific Workflow And Provenance

Review:

- W3C PROV;
- scientific workflow management;
- workflow provenance models;
- experiment tracking;
- DVC / MLflow-style lineage;
- reproducible computational pipelines;
- image-analysis reproducibility and metadata standards.

Answer:

- What is the minimum provenance model this app needs?
- Which provenance concepts are necessary and which are overkill for the prototype?

## Required Final Report Structure

### 1. Executive Summary

State the recommended conceptual model, architecture, and strongest paper framing.

### 2. Literature Map

Create a structured map of the literature/systems reviewed:

| Area | Key sources | Core lesson | Relevance to seg.bio |
| ---- | ----------- | ----------- | -------------------- |

### 3. Design Principles

Use a table:

| Principle | Evidence | Design implication | Priority |
| --------- | -------- | ------------------ | -------- |

Principles should be specific enough to implement.

### 4. Agent Model Recommendation

Answer:

- what the paper should call the agent;
- what product should call it;
- what it is not;
- what transfers from coding agents;
- what does not transfer.

### 5. Project Memory Recommendation

Propose a minimal but credible schema and explain why each part matters.

### 6. Inspection And Freshness Policy

Define what the agent may inspect and when it must re-inspect.

### 7. Action And Approval Model

Specify action categories, card fields, approval gates, execution boundaries, and refusal/blocker behavior.

### 8. Context Elicitation And Onboarding

Design a first-run guided intake flow for biologists.

Include example questions and "I don't know" / correction flows.

### 9. Volume State Machine

Critique and improve the candidate states.

Include transitions, evidence, approval requirements, and partial-region handling.

### 10. Case Study Recommendations

For MitoEM/MitoEM2 and TapeReader:

- say what the assistant should know;
- what it should ask;
- what it should not assume;
- what evidence it should generate.

For the third case:

- recommend one for paper prototype;
- one for reliable demo if different;
- one for long-term research if different;
- explain tradeoffs.

### 11. Evaluation Plan

Propose a realistic HCI/systems evaluation:

- participant profile;
- tasks;
- conditions/baselines;
- instrumentation/logging;
- quantitative metrics;
- qualitative interview prompts;
- defensible claims;
- claims to avoid.

### 12. Implementation Roadmap From Literature

Prioritize improvements:

- immediate prototype improvements;
- paper-demo requirements;
- production requirements;
- research extensions.

For each, include:

- user value;
- system change;
- what evidence/logging it needs;
- how to evaluate it.

### 13. Open Questions

List decisions the team must make.

## Citation Requirements

- Include links for every cited paper/system.
- Prefer peer-reviewed papers, official docs, and primary project docs.
- For product references such as Codex/Claude Code/Copilot/Cursor, treat them as design-pattern examples, not scientific validation.
- Be careful with publication dates and versions.
- If a source is uncertain, say so.

## Output Style

- Be concrete and implementation-oriented.
- Avoid generic phrases like "use RAG" unless you specify what gets retrieved, when, and how freshness is handled.
- Do not dump huge JSON unless it helps implementation.
- Use markdown tables where they improve clarity.
- End with a concise recommendation paragraph.

## Final Recommendation Shape

End with a recommendation similar in concreteness to:

> Build the assistant as a workflow-aware, approval-gated project operator. The central abstraction is not chat history; it is project memory plus action proposals. Chat is the conversational surface. Project memory is the source of truth. Action cards are the bridge from intent to bounded execution. Evidence events are the paper-grade provenance layer.

You may change the wording if your literature review suggests a better framing, but the final recommendation must be equally concrete.
