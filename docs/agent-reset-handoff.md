# seg.bio: May 5 baseline, project manager and task agents

**Latest:** [Local model-driven project manager and specialists](agent-team-model-layer.md).
Qwen3:4b is installed locally; ordinary chat now plans tasks, invokes bounded
read-only specialist tools, and synthesizes app recommendations. The scaffold
record below is historical; the model-layer document describes current behavior.
[Baseline repairs and verified CPU run](baseline-working-state.md) remain in place.
The launcher now includes the compute worker; the older reset-only verification
below describes the state before that repair pass.

Direction confirmed by Adam on September 15, 2026. This document supersedes older
DSL/DAG-oriented implementation priorities and the stale branch instructions in
`remote-codex-handoff.md`. The presentation is context, not an implementation spec.

## Active checkout

- Repository: https://github.com/PytorchConnectomics/pytc-client
- Active local checkout: `/Users/adamg/seg.bio/pytc-agent-prototype`
- Branch: `feat/project-manager-agents`
- Baseline: `c151bf9571a0bfba924df9195dad470839e26b1e`, May 5, 2026.
- The user selected the earlier proofreading/progress UI in the slides. The newer
  chat screenshot did not change which checkpoint they wanted.
- Local API: `http://127.0.0.1:4242`; browser: `http://127.0.0.1:3001`.
- No production deployment or remote branch push is implied by this handoff.

## Decision

Grace wants a project manager coordinating task-specific agents. DSL/DAG integration
is not a prerequisite or the contribution around which to organize the app. Retain
the biomedical process: manual labelling/proofreading, retraining, running an updated
model, then further proofreading or downstream science. Concentrate on context,
coordination and usable tools.

## What the baseline actually contains

`server_api/chatbot/chatbot.py::build_chain` constructs an LLM supervisor and separate
training/inference agents with different tool lists. Delegation invokes a specialist
and returns its response to the supervisor. This path needs Ollama, model weights and
the documentation index. It is mostly configuration/documentation assistance.

`server_api/workflows/router.py::query_workflow_agent` is a separate, largely
monolithic workflow router. It reads project state and returns concrete app actions,
proposals and command blocks. Optional semantic classification uses a model, but
recognizable app tasks have deterministic handlers. Existing plan/step records support
planning previews and approval state. They do not by themselves prove autonomous
multiagent execution or recovery.

The important gap is between the LLM specialist path and the stateful app-action path.
Do not present role labels, a trace card or a deterministic action router alone as a
completed multiagent implementation.

## First changes from baseline

- Browser startup resumes the saved workflow and remounts its project. It no longer
  resets the file workspace or creates a fresh workflow on every reload.
- The explicit New project action remains available.
- `scripts/seed_agent_demo.py` creates the demonstration project only if no guest
  workflow exists. It refuses to reset existing work and validates matching 3D TIFFs.
- `scripts/start_agent_prototype.sh` starts the API and browser app, checks ports,
  reports logs and cleans up its own child services.
- No loop DSL/compiler or later Loop UI was copied into this branch.

## Proposed next implementation increment

Keep one project manager as the conversation owner. It should delegate finite tasks
and integrate results rather than run every task itself.

| Role | Bounded responsibility | Result to return |
|---|---|---|
| Project manager | Retain the scientific objective, choose the next task, track outstanding work and integrate specialist results | Short explanation and next action |
| Data/visualization specialist | Inspect available volumes, identify image/label pairs, open relevant views | Verified paths, geometry, observations and blockers |
| Annotation specialist | Locate requested regions, open proofreading and summarize saved corrections | Region references, correction artifacts and remaining review needs |
| Model specialist | Configure training/inference and track approved runs | Proposed settings, job status, model/prediction artifacts and errors |

These boundaries are a starting proposal. Begin with one real delegation, such as a
project-manager request to inspect the NucMM image/label pair, before implementing all
roles. Existing training/inference agents may remain separate if that simplifies tool
ownership. Parallel agents are useful only for independent tasks.

Each task needs an ID, goal, owning project, selected input artifacts, assigned role,
status, bounded tool access, result and failure reason. Give specialists only the
relevant project snapshot. Return structured observations, artifacts and proposed app
actions, plus a concise summary. The project manager integrates results into shared
state. Recheck state before applying a result if the project changed during the task.

The existing app routines should execute actions and report their actual results.
Labels need human review; long compute and artifact-changing actions retain the
existing user-action/approval controls. Tool failure must remain visible. A failed
specialist must not become a fabricated success in the manager's response.

UI target: one chat entry point with compact delegation/status details that can be
expanded. Avoid separate chat windows for every specialist and excessive role badges.

## Evaluation and literature discussion for another machine

Questions to resolve before committing to an agent framework:

1. Does manager/specialist delegation improve performance or usability over one agent
   with the same tools and budget?
2. Which specialist boundaries reduce context load and tool errors?
3. What belongs in persistent project state versus temporary task context?
4. How should interruptions, stale results and failed jobs resume?
5. What trace information helps a researcher understand responsibility and progress?

Review manager–worker, agents-as-tools and handoff patterns, then scientific workflow
assistants and human–agent coordination work. These are research questions, not a
completed literature review or novelty claim. Use primary papers and official framework
documentation, and distinguish research evidence from vendor design advice.

## Local demo and portability

This host reuses installed dependencies via ignored `.venv` and `client/node_modules`
symlinks. These are not portable. On another machine, install dependencies using this
checkout's `pyproject.toml`/`uv.lock` and `client/package-lock.json`; see bootstrap scripts.
The historical source uses a working-directory-relative SQLite database at
`server_api/auth/sql_app.db`. Run the supplied scripts from this checkout. Do not share
the active loop prototype's database or worker accidentally.

Supply the same NucMM crop as `uploads/NucMM/image.tif` and `labels.tif`, or pass paths:

```bash
.venv/bin/python scripts/seed_agent_demo.py --image /path/image.tif --labels /path/labels.tif
bash scripts/start_agent_prototype.sh
```

The demo crop is 64 × 96 × 96 (ZYX), with 23 nonzero nucleus IDs and 720 nm isotropic
voxel spacing. It is the published-label demonstration shown in the historical slides,
not a scientifically proofread result. Data and model weights are not committed.

The launcher starts only UI/API. A PyTC worker is separate, normally on 4243, configured
through `PYTC_WORKER_URL`. LLM delegation additionally needs the configured Ollama chat
model, embeddings and FAISS index. Verify available hardware/models on the demo host.
Never equate a successful deterministic chat action with an LLM delegation test.

A live public demo still needs a deployment host, authentication/access decision,
persistent storage, verified worker/model endpoints and a rehearsed dataset. Prepare
those choices in the other-machine discussion rather than treating localhost as hosted.

Demo acceptance sequence: reopen the project, ask the manager to inspect the data,
observe a real specialist invocation and result, open proofreading, save a deliberate
edit, configure a small run, approve it, show actual completion, inspect predictions,
reload, and resume. Validate every claimed action; use a separate engineering fixture
for edits made by automated tests.

## Recovery

The later work remains untouched at `/Users/adamg/seg.bio/pytc-loop-prototype`.
`archive/loop-before-agent-reset-20260915` records its committed head `7f7d808`.
The archive directory `/Users/adamg/seg.bio/checkpoints/2026-09-15-loop-retired` contains
its full tracked/nonignored file snapshot, binary tracked diff, status and SHA-256
manifest. Ignored data, databases and environments remain in that original checkout.
The new development branch starts from May 5, not from the archived loop commit.

## Verification on September 15

- WorkflowContext test suite: 12 passing, including reload persistence and existing
  action/proposal behavior.
- The seed script created the 23-instance fixture; a second invocation retained it.
- Browser check: project ID survived reload; chat returned `start_proofreading`, the
  existing approval was accepted, and the real 23-instance editor loaded. No browser
  page errors. This opened a proofreading session but changed no labels and ran no
  compute. `scripts/check_agent_baseline.cjs` reproduces the check with Playwright.
- UI compiled with existing warnings. Full training/inference and LLM delegation were
  not tested in this reset. This is a restored development baseline, not an accepted
  end-to-end multiagent demonstration.

## Transfer to the other machine

A local Git bundle is available in the sibling `checkpoints/2026-09-15-loop-retired`
directory as `project-manager-agents.bundle`. It contains the new branch's change
relative to the May 5 baseline. After transferring that bundle to a machine with the
repository and base commit, fetch its `feat/project-manager-agents` branch and create
a local worktree from it. The bundle excludes datasets, model weights, environment
symlinks and databases. The branch has not been pushed to GitHub in this reset.
