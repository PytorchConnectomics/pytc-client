# Deep Research Task: Agentic Bioimage Segmentation Workflow Assistant

## Purpose

Prepare a literature and systems review for an agentic workflow assistant inside PyTC Client / seg.bio. The goal is not to implement code. The goal is to gather high-quality context that can be fed back into an engineering agent to synthesize product, architecture, and paper-writing decisions.

The research should answer: what should this app become, what prior work should it cite or learn from, and what implementation patterns are proven enough to borrow?

## Project Context

We are building an interactive client for biomedical/connectomics image segmentation workflows. The app wraps PyTorch Connectomics-style model training, inference, visualization, proofreading, evaluation, and project tracking behind a guided UI and a workflow-aware chat assistant.

The current prototype is served at:

- Demo: `https://demo.seg.bio`
- Main app repository: `https://github.com/PytorchConnectomics/pytc-client`
- Upstream PyTorch Connectomics repository: `https://github.com/PytorchConnectomics/pytorch_connectomics`

Current local demo checkout:

- `/home/weidf/deploy/pytc-client-demo2`

The intended user is a biologist or neuroscience lab user who has volumetric microscopy data and needs to train, run, inspect, proofread, and evaluate segmentation models without being forced to understand every software/configuration detail upfront.

## What The Prototype Currently Does

The app has modules for:

- Files: mount and inspect a project directory.
- Visualize: open image and label volumes in Neuroglancer.
- Train Model: configure and launch PyTorch Connectomics training.
- Run Model: configure and launch inference.
- Progress: track volume-level status across ground-truth, draft/unproofread segmentation, and missing segmentation.
- Proofread: inspect and correct mask instances.
- Assistant: chat with a workflow-aware agent that can propose direct app actions.

The Monitor tab has been sunset for now; runtime status/log links should live with Train Model or Run Model.

Recent project direction:

- The assistant should feel like a normal helpful chatbot on the surface, not an internal planner.
- Mechanical details should be available in expandable traces like “What I checked,” not front-loaded in every chat answer.
- The agent should continually update its understanding of the mounted project by inspecting files, manifests, progress state, workflow metadata, and user corrections.
- The initial project setup should not strand biologists in a blank text box. It should guide them through context with concrete questions and auto-detected facts.
- The app should distinguish volumes that are:
  - fully good ground truth,
  - segmented but still needing proofreading,
  - image-only with no segmentation yet,
  - ignored or out of scope.
- Training should be able to use multiple confirmed ground-truth volumes and then segment remaining image-only volumes.

## Current Demo Project Content

The active demo project is a MitoEM2.0-style progress fixture:

- Local path: `/home/weidf/demo_data/mitoem2_progress_demo`
- Title: `MitoEM2.0 Progress Demo`
- Dataset family: MitoEM2.0 / ssSEM mitochondria segmentation.
- Context currently used by the app:
  - imaging modality: EM / ssSEM
  - target structure: mitochondria
  - preferred optimization: accuracy
  - voxel size: roughly `30 x 8 x 8 nm` in z,y,x
- Structure:
  - `data/image/`: 6 image volumes
  - `data/seg/`: 4 segmentation volumes
  - `configs/MitoEM2-Pyra-Demo-BC.yaml`
  - `project_manifest.json`
  - `notes/`
  - `snapshots/`
- Initial progress state:
  - 2 volumes are curated/ground-truth quality
  - 2 volumes have draft segmentation needing proofreading
  - 2 volumes have no segmentation yet

The desired workflow is:

1. Mount a project.
2. App mechanically inspects what is present.
3. User confirms biological/project context with minimal typing.
4. User views/proofreads available labels.
5. User marks good volumes as ground truth.
6. Agent proposes training from ground-truth volumes.
7. App trains/runs model on remaining image-only volumes.
8. User reviews/proofreads new predictions.
9. Progress tracker updates continuously.

## Repositories And Artifacts To Inspect

### Primary repositories

- `https://github.com/PytorchConnectomics/pytc-client`
  - Look for: workflow agent implementation, project mounting, Neuroglancer integration, progress tracker, proofreading UI, training/inference orchestration, evidence logs.
- `https://github.com/PytorchConnectomics/pytorch_connectomics`
  - Look for: training/inference config patterns, supported datasets, metrics, model tasks, docs/tutorials, current v2 direction.

### Relevant docs in this repo

Inspect these first if available:

- `docs/agent-role-spec.md`
- `docs/prototype-completion-roadmap.md`
- `docs/research/pytc-prepilot-dataset-stress-test.md`
- `docs/research/tochi-hci-prototype-takeaways.md`
- `docs/research/claude-code-agent-patterns.md`
- `docs/codex-working-memory/research-log.md`
- `docs/codex-working-memory/progress-log.md`
- `docs/codex-working-memory/workflow-spine-spec.md`

### Dataset/reference ecosystems to inspect

- MitoEM and MitoEM2.0:
  - Hugging Face datasets under `pytc/MitoEM` and `pytc/MitoEM2.0`
  - PyTorch Connectomics configs/tutorials for mitochondria segmentation
- Lucchi / Lucchi++:
  - classic mitochondria EM segmentation benchmark
  - PyTC tutorial datasets/configs
- SNEMI3D:
  - neuron segmentation benchmark
  - affinity output and postprocessing patterns
- CREMI:
  - synaptic cleft/neuron/synapse benchmark
  - multi-volume HDF5 workflows
- NucMM:
  - nuclei segmentation across mouse/zebrafish
  - tests project generality beyond mitochondria/connectomics

## Core Research Questions

### 1. Human-agent interaction for scientific workflows

Find literature on:

- agentic interfaces for domain experts,
- human-in-the-loop scientific workflows,
- mixed-initiative systems,
- LLM agents for data analysis or laboratory work,
- how to expose agent reasoning without overwhelming users,
- how to avoid “blank page” onboarding for nontechnical experts.

Specific angle: how should a system elicit project context from a biologist who knows the science but may not know what the software needs?

### 2. Bioimage segmentation UX and workflow tools

Find relevant tools and papers around:

- ilastik
- CellProfiler
- napari and napari plugins
- Fiji/ImageJ segmentation workflows
- Neuroglancer use in connectomics
- webKnossos
- VAST / proofreading tools
- MoBIE / BigDataViewer if relevant
- other interactive segmentation/proofreading systems

Focus on:

- how users import projects,
- how tools represent datasets and labels,
- how proofreading status is tracked,
- how model training/inference loops are made understandable.

### 3. Connectomics and volumetric segmentation workflows

Review PyTorch Connectomics and related connectomics workflows:

- semantic segmentation vs affinity/instance segmentation,
- common model outputs,
- expected file formats and folder layouts,
- training/inference/evaluation lifecycle,
- metrics used for mitochondria, nuclei, neurons, synapses,
- how proofread labels become new training data.

Output should clearly distinguish what is universal vs connectomics-specific.

### 4. Agent architecture and project-context memory

Find patterns for:

- tool-using agents that inspect local files/project state,
- persistent project memory,
- retrieval over project artifacts,
- structured context/state graphs,
- durable action proposals and approval cards,
- separation between visible response and hidden trace,
- agent plans vs direct app actions.

Compare:

- Claude Code / Codex-style expandable thinking traces,
- Cursor/Copilot-style coding assistants,
- data-analysis agents,
- domain workflow copilots.

Specific question: what is the canonical pattern for keeping an agent’s project context fresh as files and user decisions change?

### 5. Benchmarks and datasets for evaluating this prototype

Identify benchmark/project fixtures we can use to test the workflow:

- small enough to run or stage locally,
- has raw data and masks,
- can simulate partially proofread, draft, and missing segmentations,
- representative of real PyTC workflows.

For each candidate dataset, report:

- source URL,
- license/access constraints,
- expected file format,
- ground-truth availability,
- segmentation task,
- recommended PyTC config if known,
- whether it is useful for a demo, a paper case study, or a stress test.

### 6. Paper positioning

Find likely paper framing:

- HCI / CHI / UIST-style human-agent collaboration for scientific software?
- Bioimage analysis tool paper?
- Connectomics workflow systems paper?
- Demo/prototype paper?

The app’s central claim is not “new segmentation model.” It is closer to:

- agent-guided segmentation workflow orchestration,
- project-context-aware biomedical image segmentation client,
- human-in-the-loop proofreading/training loop with persistent workflow memory,
- reducing software/configuration burden for biology users.

Find prior work and gaps supporting or challenging that claim.

## Output Required From The Research Agent

Produce a single markdown report with these sections:

1. **Executive Summary**
   - 10-15 bullet points with the most actionable findings.

2. **Related Work Map**
   - Cluster papers/tools by theme.
   - Include citations, links, and 1-3 sentence relevance notes for each.

3. **Product Implications**
   - Concrete design recommendations for this app.
   - Separate “do now,” “later,” and “avoid.”

4. **Agent Architecture Implications**
   - Recommended pattern for project context ingestion, memory, tool use, traces, and action proposals.
   - Call out which patterns are established vs speculative.

5. **Bioimage Workflow Implications**
   - What the app must support for mitochondria, nuclei, neuron/synapse, and general volumetric segmentation workflows.

6. **Dataset / Benchmark Recommendations**
   - Table of candidate datasets.
   - Include which ones best support:
     - demo reliability,
     - paper case study,
     - stress testing,
     - partial-label progress workflow.

7. **Paper Positioning**
   - Candidate paper thesis.
   - Best venue categories.
   - Related-work outline.
   - Claims that are defensible vs claims to avoid.

8. **Open Questions For The Engineering Agent**
   - Questions that need implementation judgment, not more literature.

9. **Annotated Bibliography**
   - Full citations or stable links.
   - Short annotation for each source.

## Research Quality Bar

- Prefer primary sources: papers, official docs, benchmark pages, official GitHub repositories.
- Include URLs for every important source.
- Separate facts from interpretation.
- Avoid generic “LLM agents are useful” summaries; tie every point back to this app.
- When citing tools, describe their actual workflow model, not just their feature list.
- Note if a source is outdated or if a tool is no longer maintained.
- Call out contradictions or tradeoffs.

## Known Current Pain Points To Keep In Mind

- The assistant has often sounded too robotic or planner-like.
- The assistant previously failed to inspect mounted project files deeply enough before answering.
- Blank project-context text boxes are intimidating for biology users.
- Biologists may know the relevant experimental context but may not know how to express it in software terms.
- The app needs to continuously reconcile:
  - what files exist,
  - what the user says,
  - what has been proofread,
  - what is eligible for training,
  - what has already been inferred,
  - what evidence is stored for reproducibility.
- The agent should propose direct app routines, but not silently mutate artifacts or run expensive jobs without approval.
- The workflow needs to support multi-volume training, not just single image/label pairs.

## Deliverable Style

Write for an engineering + HCI synthesis reader. The final report should be precise enough that another agent can turn it into implementation tasks, but broad enough to include literature and design framing.

Do not write marketing copy. Do not overclaim. Be concrete.
