# Yixiao TapeReader/XRI Case Study Protocol - 2026-06-04

## Purpose

This protocol defines a one-hour case study for the Yixiao TapeReader/XRI fixture in seg.bio. It is written for the facilitator and paper team, not as a participant-facing script.

The case study should demonstrate that seg.bio is becoming a workflow-aware, mixed-initiative assistant for biomedical volume segmentation. The core claim is not that seg.bio improves segmentation accuracy by itself. The core claim is that the system helps a domain expert coordinate project context, volume state, inspection, proofreading, training, inference preparation, and evidence capture across a fragmented workflow.

## Case Study Claim Boundary

### Claims This Study Can Support

- The app can inspect a mounted project and construct useful shared project context.
- The app can maintain a visible volume-level workflow state.
- The assistant can answer project and workflow questions from inspected state.
- The assistant can propose bounded app actions instead of giving generic instructions.
- Costly or mutating actions can be approval-gated.
- Users can edit agent-proposed action fields before approving.
- The progress view and assistant can refer to the same canonical volume split.
- Evidence export can capture workflow state and action provenance.

### Claims This Study Should Not Make Alone

- The trained model improves over TapeReader or PyTC baselines.
- The system reduces total biological analysis time in all settings.
- The proofreading editor is production-grade.
- The app faithfully reproduces every detail of the original TapeReader paper pipeline.
- The agent is autonomous or safe for unreviewed execution.

## Participant

Primary participant:

- Yixiao, a domain expert connected to the TapeReader/CytoTape XRI workflow.

Desired role in the study:

- Treat Yixiao as the scientific owner of the dataset and target task.
- Ask her to judge whether the app's inferred project context, status split, and proposed next actions match how she thinks about the workflow.
- Do not ask her to debug implementation details unless the app visibly fails.

## Study Setup

Demo URL:

```text
https://demo.seg.bio
```

Project root:

```text
/home/weidf/demo_data/yixiao_tapereader_xri_case_study
```

Expected initial state:

| Category | Expected Value |
| --- | --- |
| Project | Yixiao TapeReader XRI Case Study |
| Modality | X-ray / XRI volumetric microscopy |
| Target | CytoTape fibres |
| Voxel size | 40 x 16.3 x 16.3 nm in z,y,x |
| Total tracked volumes | 10 |
| Fully good / ground truth | 6 |
| Needs proofreading | 2 |
| No segmentation | 2 |
| Training policy | Train only on confirmed ground-truth masks |

Volume split:

| State | Volumes |
| --- | --- |
| Ground truth | `1`, `2`, `3`, `4_1`, `4_2`, `4_3` |
| Needs proofreading | `5_1`, `5_2` |
| Image only | `6_1`, `6_2` |

## Taxonomy Of Study Tasks

### 1. Project Common Ground

Goal:

- Determine whether the app can inspect the project and summarize it in terms that match the domain expert's understanding.

What Yixiao does:

- Opens the demo.
- Mounts or opens the suggested Yixiao project.
- Reviews the setup/project context surfaced by the app.
- Uses the assistant to ask what the project is.

What we ask Yixiao:

1. "Does this summary match what you think this dataset is?"
2. "What is missing from this summary that you would want the agent to know before acting?"
3. "Are any of these terms wrong or too software-centric?"
4. "Would this setup screen help you get started, or would it still feel like a blank prompt?"

Specific prompts to ask the in-app agent:

```text
What project are we looking at?
```

```text
What are the files and volumes in this project?
```

```text
What do you know about the voxel size and target structure?
```

Evidence to capture:

- Screenshot of setup/project context.
- Assistant response.
- "What I checked" or operational trace content.
- Any user correction to project context.

Paper construct:

- Shared context / common ground.
- Initial interaction support.
- Reduced blank-box onboarding.

### 2. Volume State And Workflow Progress

Goal:

- Determine whether the volume-level progress view is understandable and useful.

What Yixiao does:

- Opens the Progress view.
- Reviews the 10-volume status split.
- Clicks/filter/sorts if useful.
- Identifies whether `5_1`, `5_2`, `6_1`, and `6_2` are correctly characterized.

What we ask Yixiao:

1. "Do these volume statuses match your mental model of the project?"
2. "What would you call these states in your own words?"
3. "Which of these statuses would you trust for training?"
4. "Are the counts enough, or do you need examples/thumbnails/quality indicators?"
5. "Would you expect this screen to be the source of truth for the agent?"

Specific prompts to ask the in-app agent:

```text
How many volumes are ready for training, and which ones should be left out?
```

```text
Which volumes still need human attention?
```

```text
What would be the safest next step in this project?
```

Evidence to capture:

- Progress summary counts.
- Volume table status rows.
- Agent response about train-eligible and excluded volumes.
- Any mismatch between progress view and agent response.

Paper construct:

- Workflow state legibility.
- Human-agent shared reference.
- Trust calibration around labels.

### 3. Data Inspection / Visualization

Goal:

- Determine whether the app and assistant can move from project state into visual inspection.

What Yixiao does:

- Asks the agent to show sample data.
- Clicks the resulting action card or uses Visualize.
- Inspects a ground-truth pair.
- Optionally asks to view another volume or a proofreading target.

What we ask Yixiao:

1. "Is this the right kind of visual context for deciding what to do next?"
2. "Are the voxel scale and orientation believable?"
3. "Does the viewer make clear which image and mask are currently open?"
4. "Would you expect the agent to automatically choose this first example?"

Specific prompts to ask the in-app agent:

```text
Can we look at one fully good example?
```

```text
Can you open a draft mask that needs proofreading?
```

```text
What am I looking at here?
```

Evidence to capture:

- Neuroglancer URL.
- Active image and label paths.
- Agent explanation of why it chose the volume.
- Any scale/orientation correction from Yixiao.

Paper construct:

- Mixed-initiative handoff from chat to visual tool.
- Context-aware visualization action.
- Progressive disclosure of inspected evidence.

### 4. Proofreading Decision

Goal:

- Determine whether the system correctly distinguishes draft masks from training-ready ground truth.

What Yixiao does:

- Reviews the draft-mask volumes `5_1` and `5_2`.
- Says whether those masks are actually draft, accepted, or unusable.
- Optionally promotes one draft mask to training-ready if appropriate for the simulated run.

What we ask Yixiao:

1. "Would you call these masks draft segmentations, preliminary labels, or ground truth?"
2. "What evidence would you need before promoting one to training?"
3. "Would you trust the agent to promote a mask automatically?"
4. "What should happen if you disagree with the agent's status?"

Specific prompts to ask the in-app agent:

```text
Which masks should I proofread before training?
```

```text
Should these draft masks be used for training yet?
```

```text
If I mark 5_1 as good, how does that change the training set?
```

Evidence to capture:

- Current status before promotion.
- User's judgment.
- Status change event if performed.
- Training proposal count before and after promotion.

Paper construct:

- Human correction loop.
- Label trust and training eligibility.
- Approval-gated state mutation.

### 5. Training Proposal

Goal:

- Determine whether the assistant can stage a multi-volume training job from trusted ground truth only.

What Yixiao does:

- Asks the agent to train a model using the trusted labels.
- Reviews the proposed training card.
- Checks selected image root, label root, config, output path, and excluded volumes.
- Edits at least one auto-filled field if possible, or confirms that editing is discoverable.
- Does not need to actually launch a long GPU job unless the facilitator decides to.

What we ask Yixiao:

1. "Does this training proposal include the right volumes?"
2. "Is it clear why the draft and image-only volumes were excluded?"
3. "Is the proposed config meaningful to you, or does it need a domain-readable explanation?"
4. "Can you tell what will happen if you approve?"
5. "Would you feel comfortable editing the proposed fields before approving?"

Specific prompts to ask the in-app agent:

```text
Train a model using only the fully good ground-truth volumes.
```

```text
Why did you leave out 5_1, 5_2, 6_1, and 6_2?
```

```text
What exactly will this training run use and produce?
```

Evidence to capture:

- Training action card.
- Included/excluded volume counts.
- Editable fields.
- Approval gate.
- Operational trace.
- Generated subset manifest.

Paper construct:

- Bounded agentic action.
- Approval-gated execution.
- Trust-aware data selection.
- Editable automation.

### 6. Inference Planning

Goal:

- Determine whether the assistant can identify image-only targets and prepare downstream inference without leaking withheld labels.

What Yixiao does:

- Asks what should happen after training.
- Asks how to segment the remaining image-only volumes.
- Reviews that `6_1` and `6_2` are treated as inference targets, not training labels.

What we ask Yixiao:

1. "Does this match how you would use a trained model on the rest of the data?"
2. "What outputs would you expect after inference?"
3. "How should predictions be marked before and after proofreading?"
4. "What would you want the app to do with low-confidence predictions?"

Specific prompts to ask the in-app agent:

```text
After training, which volumes should we run inference on?
```

```text
Do we have labels for 6_1 and 6_2?
```

```text
What should happen to predictions before they become training data?
```

Evidence to capture:

- Agent response naming `6_1` and `6_2`.
- Confirmation that withheld labels are not used.
- Proposed inference action, if available.
- State distinction between prediction and accepted reference.

Paper construct:

- State-aware planning.
- Leakage prevention.
- Separation of predictions and ground truth.

### 7. Evidence / Provenance Export

Goal:

- Determine whether the workflow can produce a useful record of what happened.

What Yixiao does:

- Asks what evidence has been captured.
- Optionally exports a bundle.
- Reviews whether the exported summary would help reconstruct the workflow.

What we ask Yixiao:

1. "Would this be enough for you or a collaborator to understand what was done?"
2. "What else would you need in the provenance bundle?"
3. "Which artifacts matter most for a paper figure or methods section?"
4. "Should the evidence be more human-readable, machine-readable, or both?"

Specific prompts to ask the in-app agent:

```text
What have we done so far in this workflow?
```

```text
Can you summarize the evidence for this case-study session?
```

```text
What would go into an export bundle?
```

Evidence to capture:

- Export endpoint result.
- Bundle path.
- Included events/artifacts/runs/proposals.
- Any missing provenance noted by Yixiao.

Paper construct:

- Reproducible workflow evidence.
- Provenance ledger.
- Paper-grade audit trail.

### 8. Overall Reflection

Goal:

- Get qualitative feedback aligned with the paper's HCI claims.

What we ask Yixiao:

1. "Where did the app feel like it understood the project?"
2. "Where did it feel brittle or generic?"
3. "Which agent suggestions saved effort?"
4. "Which suggestions would you not trust?"
5. "What context did you still have to carry in your head?"
6. "What would make this useful in a real lab workflow?"
7. "Would you prefer this over a manual-only PyTC/Neuroglancer workflow for this task? Why or why not?"
8. "If you handed this project to someone else, would this progress/evidence state help them pick up the work?"

Paper construct:

- Perceived usefulness.
- Trust calibration.
- Workflow handoff.
- Common ground.
- Remaining design gaps.

## Suggested One-Hour Schedule

| Time | Segment | Activity |
| --- | --- | --- |
| 0-5 min | Intro | Explain that this is a workflow-coordination prototype, not a model-accuracy benchmark. |
| 5-12 min | Project setup | Open/mount Yixiao project and review inferred context. |
| 12-20 min | Progress state | Inspect 10-volume status split and discuss training eligibility. |
| 20-30 min | Visualization | Open one ground-truth pair and one draft/proofreading target. |
| 30-38 min | Proofreading status | Discuss or simulate promoting a draft mask. |
| 38-48 min | Training proposal | Ask the agent to stage training from trusted ground truth; review/edit proposal. |
| 48-53 min | Inference planning | Ask what happens to image-only targets after training. |
| 53-57 min | Evidence export | Export or inspect session provenance. |
| 57-60 min | Reflection | Ask final study questions. |

## Facilitator Checklist

Before Yixiao arrives:

- Run `scripts/manage_demo_instance.py status`.
- Run `scripts/run_yixiao_case_study_smoke.py --prepare-live`.
- Run `scripts/inspect_demo_instance.py`.
- Confirm `https://demo.seg.bio` loads.
- Confirm current workflow is Yixiao with 10 volumes and 6/2/2 split.
- Confirm Neuroglancer URL starts with `https://demo.seg.bio/neuroglancer`.
- Keep terminal open with logs available.

During the study:

- Do not over-explain how the app is supposed to work before Yixiao reacts.
- Ask her to think aloud.
- When the agent gives a proposal, ask her what she thinks will happen before clicking.
- If a response is wrong, ask what she expected and record the mismatch.
- Avoid running long GPU jobs unless the study goal explicitly includes runtime behavior.

After the study:

- Export evidence bundle.
- Save screenshots of progress, proposal card, and any important agent responses.
- Reset the case-study workflow to the initial 6/2/2 state.
- Add notes to the progress log.

## Success Criteria

The case study is successful if it produces evidence for at least these points:

1. Yixiao can understand the app's inferred project context and correct it where needed.
2. The 10-volume progress split is legible and scientifically meaningful.
3. The assistant can correctly answer project, progress, visualization, training, and inference questions from workflow state.
4. The training proposal excludes draft and image-only volumes.
5. The user can inspect and edit an action proposal before approval.
6. The system captures an evidence trail for the session.
7. The study identifies concrete gaps for the next prototype iteration.

## Failure Modes To Watch

- Agent answers from stale context after progress changes.
- Agent treats draft masks as ground truth.
- Agent proposes training on image-only targets.
- Action card fields are clipped or hard to edit.
- Neuroglancer URL uses local or insecure paths.
- Progress view and agent response disagree.
- User cannot tell what approving an action will do.
- Evidence export is too low-level for paper use.
