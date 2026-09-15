# Project manager and specialist scaffold

**Historical scaffold record. The active launcher now uses the [local model layer](agent-team-model-layer.md).**

September 15, 2026. Built on the repaired May 5 baseline; proofreading UI is unchanged.

## Try it

Open the assistant, choose **Team**, then **Check project**. The scope selector can
request the whole project or one specialist. Typing `/team` also opens this panel.
The manager presents a summary and deduplicated proposed next actions. Actions are
resolved by the server against the saved task and current input fingerprint, then
sent directly to the existing app harness. View data loads the viewer in one click;
opening proofreading retains its approval step. Preparing training/inference fills
forms without launching compute.

You can also type “Ask the data specialist to inspect the current project” into
chat. This creates a persisted task and opens its results. “What did the data
specialist find?” retrieves saved evidence without rerunning the worker. Chat
responses link back to their task results. These are explicit rule-based request
patterns, not unrestricted model reasoning.

The header names the active workflow. Browsing another folder does not switch that
workflow; project selection and directory browsing remain distinct. Other checks
can reopen full historical task context and results.

## What actually runs

This is a **tool-backed coordination scaffold**, not an LLM multiagent demonstration.
The project manager uses an explicit scope policy to dispatch separate worker
functions. There are no local Ollama model weights installed. No model calls,
autonomous reasoning, self-directed delegation, or improved segmentation quality
are claimed by this increment.

- **Data specialist:** reads registered TIFF headers, compares image/label geometry,
  and counts nonzero integer label IDs within a 64 MiB decoded-volume budget.
- **Annotation specialist:** checks whether source masks and saved correction files
  exist. It does not certify human review or change masks.
- **Model specialist:** checks registered config, checkpoint and prediction files.
  It does not load weights, certify compatibility, or launch compute.
- **Project manager:** supplies selected project context, collects results, highlights
  failures/blockers, and combines next-step proposals with their source task IDs.
  If the requested data check fails, it withholds next-step proposals.

Each task has an ID, project, role, goal, bounded tool set, selected context, status,
timestamps and structured observations/facts/blockers/actions. Workers can inspect
only their supplied inputs through their hard-coded role implementation. They do
not receive chat history, arbitrary tool execution, or workflow mutation tools.

The API persists runs/tasks in `workflow_team_runs` and emits delegation/completion
workflow events. UI polling shows saved status; a reload retrieves the same records.
An input fingerprint includes project context and registered file metadata. Results
are marked stale if those values change; their action buttons are disabled. This is
a metadata-based freshness check, not a content hash or an immutable dataset version.
The downstream workflow router also evaluates current state when an action is asked
for. No specialist result is directly applied to the workflow.

A task exception remains a failed task; the manager does not fabricate success.
A server restart marks unfinished in-process tasks interrupted. A fresh check can be
requested. Request keys deduplicate sequential retries. This is a single API-process
prototype, not a distributed queue or a fault-tolerant scheduler.

## Code

- `server_api/workflows/agent_team.py`: request/result storage, snapshot creation,
  role workers, manager integration, API, restart recovery.
- `client/src/components/chat/AgentTeamPanel.js`: compact team view, polling, evidence,
  freshness handling and action handoff.
- `client/src/components/Chatbot.js`: Team entry point and existing action routing.
- `server_api/main.py`: table/router registration and startup recovery.

## Validation

Automated checks cover real TIFF counts, unchanged labels, persisted task records,
scoped context, deduplicated proposals, event logging, stale inputs, worker failure,
restart interruption, invalid roles, and project ownership. Frontend checks cover
retrieval, action routing, stale-action disabling, request errors and switching
projects while a request is outstanding. Existing workflow/chat regression tests
remain part of this pass. Final results: **53 backend tests and 29 frontend tests
passed** (82 total).

The browser demo uses the original NucMM project read-only: it reports the
64 × 96 × 96 crop, 23 label IDs, no registered saved corrections, and the CPU preset.
The separate engineering project's training artifacts are not attributed to NucMM.
A browser test followed the manager recommendation through the existing action
proposal/approval and opened the real 23-instance proofreading editor. The team
results were also retrieved after a server restart and page reload.

## Next increment

Replace the fixed dispatch/synthesis policy with a model-backed project manager and
bounded model-backed workers, preserving the same task/result contracts and app
execution controls. Add structured model-output validation, model/provider metadata,
time/tool budgets, cancellation and explicit failure handling. Then compare the
same tasks against a single agent with the same tools. The older Ollama specialist
path remains separate; this scaffold does not silently route through it.

There is no dependency on the retired DSL/DAG integration or a public deployment.


## Integration verification

The previously failing natural-language request now created a data-only task in the
browser and returned the correct NucMM geometry and 23 label IDs. Its View data
button directly loaded Neuroglancer with the correct 720 nm scales. The proofreading
button directly produced the existing approval card, without a second chat query.
Relevant automated tests: 58 backend and 30 frontend passed, including the final
viewer label-provenance check. No labels were edited and no compute was launched.

After a final server restart, the browser follow-up “What did the data specialist
find?” returned the saved 64 × 96 × 96 / 23-ID evidence and linked the same task,
without creating another check. The direct proofreading approval also opened the
real 23-instance editor.
