# Local project manager and specialist agents

September 15, 2026. Active implementation on the May 5 baseline in
`feat/project-manager-agents`. Supersedes the deterministic-only status in the
[scaffold assessment](agent-team-scaffold.md).

## What runs

Ordinary project chat now invokes **Qwen3:4b through local Ollama**. The project
manager selects finite tasks for data, annotation, and model specialists. Each
specialist gets its own model calls, selected project context, and a restricted
read-only tool set. The manager receives their results and selects supported app
actions. Specialists currently execute sequentially on the same model; these are
separate role contexts, not separately trained models or parallel processes.

The flow is:

`chat → manager plan → specialist tool/interpretation loops → manager synthesis → app action`

- Data reads TIFF geometry and counts integer label IDs (64 MiB decoded count limit).
- Annotation checks registered source masks and correction artifacts.
- Model checks configuration/checkpoint/prediction files and can read the registered
  YAML configuration (128 KiB limit).
- The manager returns a recommendation with task references. App action buttons use
  existing server-resolved routes: visualization, proofreading, or preparing forms.
  They do not execute model-generated code, arbitrary paths, or automatic training.

This is a working model-driven inspection/delegation layer. It does not yet run an
open-ended scientific project, inspect biological alignment visually, evaluate
segmentation quality, or conduct autonomous retraining. The separate baseline CPU
training/inference path remains available through app controls and slash commands.

## Context and persistence

Each run snapshots the active workflow, scientific objective, and registered file
references. Specialists receive only their role's subset. The manager additionally
receives up to six recent messages from the same project/conversation and measured
observations from up to two completed checks with the same input fingerprint.
Prior generated summaries are not promoted into the measured-evidence memory.
Conversation text is still unverified context, not a source of scientific truth.

SQLite `workflow_team_runs` stores the plan, tasks, selected contexts, actual tool
results, evidence IDs, validated model outputs, durations/token counts, status,
errors, and proposed actions. The final summary updates the originating persisted
chat reply. Reloading retains task history and links back to the relevant result.
No private model reasoning is requested or displayed.

The freshness fingerprint covers project fields and file metadata, not a content
hash. It is checked during execution and again when resolving an action. Failed or
blocked tasks remain visible. Data-check failure withholds downstream actions.
Startup marks unfinished in-process work interrupted; there is no distributed queue
or automatic resumption.

## Execution constraints

Pydantic validates manager/task/result contracts. The structured-output schema
restricts tool names, evidence IDs, and action choices to those actually available;
server validation remains authoritative. Model text never becomes executable code.

Each run allows at most three specialists, three tool steps per specialist, 14
model calls, and a 240-second orchestration deadline checked between operations.
Each model response is limited to 700 output tokens with a read timeout of up to
60 seconds. Cancellation prevents subsequent calls and actions after an in-flight
request returns; it is not immediate interruption of Ollama inference. Provider
errors and invalid outputs fail visibly, without silently substituting scripted
success. These are prototype budgets, not hard real-time process termination.

Generated recommendations can still be wrong. The first live tests exposed
unsupported biological-alignment claims and invented action names. Prompts and
configuration observations were tightened, and action/evidence choices are now
constrained in the generation schema as well as checked by the server. This is
**structural validation, not a proof of factual accuracy**. Tool observations remain
separate from the agent's interpretation in the UI.

## Start and try it

Ollama must be running locally with the model installed:

```sh
ollama pull qwen3:4b
bash scripts/start_agent_prototype.sh
```

The launcher defaults `PYTC_TEAM_MODEL=qwen3:4b` and
`PYTC_TEAM_OLLAMA_URL=http://127.0.0.1:11434`. It does not automatically install model
weights. `PYTC_TEAM_MODEL="" bash scripts/start_agent_prototype.sh` explicitly selects
the older deterministic scaffold. Direct API launches must set `PYTC_TEAM_MODEL`
themselves. `/api/workflows/team-runtime` reports the configured executor/model;
it is configuration status, not a provider health probe.

Open <http://127.0.0.1:3001/>, open the assistant, and ask:

> Do a fresh whole-project check using all three specialists: data, annotation,
> and model. Read the CPU configuration. What is available, what is missing, and
> what supported app action should I take next?

The Team panel shows planning, specialist progress, synthesis, cancellation,
evidence, model activity, history, and actionable recommendations. `/team` opens it;
legacy slash commands retain their existing deterministic workflow routes.

## Code and validation

- `server_api/workflows/team_llm.py`: model adapter, schemas, planning, bounded tool
  loop and synthesis.
- `server_api/workflows/agent_team.py`: registered tools, persistence, cancellation,
  freshness checks and action resolution.
- `server_api/workflows/router.py`: ordinary chat delegation, project-scoped memory.
- `client/src/components/chat/AgentTeamPanel.js` and `Chatbot.js`: live progress,
  provenance, final reply integration and action handoff.

Tests use a provider double while executing real tools and temporary databases.
They cover successful delegation, persistence, unchanged labels, provider outages,
invalid tools/evidence/actions, duplicate roles, cancellation, stale context,
project ownership and linked chat results. Browser testing uses actual local model
calls against the original NucMM project; details are recorded below.

The local NucMM crop is 64 × 96 × 96 with 23 nonzero label IDs. Matching array shape
is not evidence that labels correctly delineate nuclei. The two-iteration CPU preset
is an engineering smoke test, not scientific model training.

Provider references: [Ollama chat API](https://docs.ollama.com/api/chat),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[Qwen3:4b model](https://ollama.com/library/qwen3:4b).

### Verified local runs

- `24503c16-251a-4301-b9a3-3a7f677a49a8`: first actual data-only model run,
  four calls. Its unsupported alignment wording motivated the grounding changes;
  retain it as historical evidence, not a scientific finding.
- `8582a650-b95f-4cad-bccd-63e368d06477`: browser request reached all three
  specialists; the model specialist invented action names and correctly failed.
- `953b6b2b-e05f-4e62-98f6-913f981d91cd`: cancelled through the browser while
  the model was active. It terminated cancelled with no proposed actions.
- `6e9a1fd1-8d90-463f-9f9e-10b5a70845d4`: final browser request completed all
  three specialists and manager synthesis, nine real model calls totaling 91.16
  seconds of model request time. Actual tools read TIFFs, correction references,
  artifact availability and the CPU YAML. The manager identified the smoke-test
  budget and proposed proofreading. Following that action and the existing app
  approval opened the actual 23-instance editor with XY/YZ/XZ and 3D views. No
  labels were changed and no compute job was launched.

The final summary still uses imprecise wording (“no correction artifacts exist in
labels” / “no checkpoint ... generated”) where the evidence establishes only that
no such artifact is **registered**. This is a known language-quality limitation of
this small model, not a verified claim about dataset history. Expanded evidence
contains the exact tool statements. A future evaluation should measure this rather
than treating one successful run as a reliability benchmark.

Validation: 109 backend tests plus five subtests passed in the broader baseline
regression pass. The subsequent manager/workflow pass passed 67 tests, including
four added validation/freshness cases. The final agent module passed all 20 tests.
The chat/team frontend pass passed 32 tests. These totals overlap and should not
be added together. Existing deprecation warnings remain.
