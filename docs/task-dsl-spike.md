# Task scripts (spike)

Branch: `spike/task-dsl`. Throwaway prototype for discussion; not reviewed for merge.

## Idea

A user asks for a task in plain words. Instead of acting directly, the agent
drafts a short **task script**. The user reads it, edits it if needed, and
approves it. Only an approved, error-free script runs.

```
task train on cluster
  image   "/projects/lab/data/raw/train-01_image.h5"
  label   "/projects/lab/data/seg/train-01_ground_truth.h5"
  preset  synthetic-tiny
  steps   100
  output  "/projects/lab/runs/train-1022-0116"
```

Four task kinds: `train`, `infer`, `evaluate`, `view`. One task per script.
`set` lines change any key of the preset's YAML config, and are checked against it
(unknown keys get a "did you mean", wrong types are flagged, and keys owned by a field
such as `steps` must be changed on that field's line):

```
  set SOLVER.BASE_LR 0.001
  set SOLVER.SAMPLES_PER_BATCH 2
```

Clicking a value in the `config.yaml` preview writes the matching `set` line, so the
script stays the single record of what ran.

The design follows Raiven (arXiv 2604.10008) and RaivenTracks (arXiv 2608.14869):

- **The LLM never writes script text.** It fills a JSON form (Ollama structured
  output), and a deterministic printer produces the script. Settings the user did
  not mention (steps, preset, output folder) come from code defaults, not the model.
- **One checker for AI and human edits.** Syntax errors, unknown fields (with
  "did you mean"), wrong types, and missing input files on the target are flagged
  per line while typing.
- **A deterministic compiler.** An approved script becomes the exact PyTC YAML,
  command, and Slurm job. The preview lists every config change and why
  (from your script / where it runs / automatic fix).
- **Talk to the script.** Questions ("why train-01?") are answered from what the
  drafter saw, and answers about a line appear in that line's margin. Feedback
  ("use train-02, 50 steps") comes back as a line diff to accept or discard; the reply
  describing a revision is written from the diff by code, so it cannot disagree with it.
- **Every approved script is kept** with the request that produced it. "My model"
  and "that prediction" resolve to outputs of earlier runs.

## Code

| File | Role |
|---|---|
| `server_api/task_dsl/language.py` | Grammar, schema, parser, checker, printer |
| `server_api/task_dsl/compiler.py` | Script → config, command, change list; automatic fixes |
| `server_api/task_dsl/drafter.py` | Request → draft (Ollama form filling, keyword fallback) |
| `server_api/task_dsl/targets.py` | Run on a Slurm cluster over SSH, or on this laptop |
| `server_api/task_dsl/router.py` | `/api/task-dsl/{schema,draft,check,run,jobs}` |
| `client/src/views/TaskScripts.js` | "Task Scripts" tab: request, editor, preview, runs |
| `tests/test_task_dsl.py` | Language and compiler tests |

## Running it

1. Copy `.task-dsl.env.example` to `.task-dsl.env` and fill in your cluster login,
   a working folder on the cluster, and the Python of a conda env with PyTorch
   Connectomics. That folder needs `pytorch_connectomics/` (this repo's pinned copy)
   and your data.
2. `scripts/task_dsl_demo.sh` (starts Ollama if needed, then the usual `scripts/dev.sh`).
3. Open the **Task Scripts** tab.

Jobs run on the `short` partition with one GPU by default. Run history lives in
`~/.pytc_task_dsl/`.

## Demo script (about 5 minutes)

Each cluster job takes about a minute end to end (80 s, 67 s, 56 s in rehearsal).
Finished runs from a rehearsal are already listed under **Runs** as a fallback.

1. Click **Train** under the request box. The AI picks the image and ground truth from
   that folder (about 6 s).
2. Ask: "why did you pick train-01?" Then: "use train-02 instead, only 50 steps, and set
   the learning rate to 0.001". Accept the diff.
3. Open **Show config.yaml** and click `SAMPLES_PER_BATCH`; type 2. A `set` line appears.
4. Break a line on purpose (e.g. `set SOLVER.BASE_RL 0.01`): the margin note says
   "Did you mean `SOLVER.BASE_LR`?" and Run is disabled. Delete the line.
5. Point at **Automatic fixes**: settings that would have crashed PyTC at run time.
6. **Run on the cluster.** About 80 s. While it runs, explain the design.
7. **Run my model**, then **Score it**: the model and prediction are filled in from the
   runs above; the score shows Dice and IoU.

## Known limits

- One task per script; no chaining inside a script yet (run history covers "my model").
- `view` on the cluster copies files to the laptop before opening Neuroglancer.
- Path checks are cached for 20 seconds.
- Approved scripts are not yet written to the workflow event ledger.
- The app's own safe training defaults (`server_pytc/services/model.py`,
  `_apply_training_safe_defaults`) set `MODEL.FILTERS` to `[8, 12, 16, 24, 32]`, which
  fails with group norm. The task-script compiler fixes this; the existing training
  tab does not.
