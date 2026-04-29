# Workflow Spine Spec

Local architecture handoff for the Workflow Spine milestone.

## Scope

The implemented spine supports:

`load data -> visualize/infer -> proofread -> export corrected masks -> stage retraining -> record evidence`

Retraining is staged, not required to complete. Evaluation is represented as a stage value but is not implemented as a real comparison workflow yet.

## Backend

### Tables

`workflow_sessions`

- `id`
- `user_id`
- `title`
- `stage`
- `dataset_path`
- `image_path`
- `label_path`
- `mask_path`
- `neuroglancer_url`
- `inference_output_path`
- `checkpoint_path`
- `proofreading_session_id`
- `corrected_mask_path`
- `training_output_path`
- `metadata_json`
- `created_at`
- `updated_at`

`workflow_events`

- `id`
- `workflow_id`
- `actor`
- `event_type`
- `stage`
- `summary`
- `payload_json`
- `approval_status`
- `created_at`

### API

- `GET /api/workflows/current`
- `PATCH /api/workflows/{id}`
- `GET /api/workflows/{id}/events`
- `POST /api/workflows/{id}/events`
- `POST /api/workflows/{id}/agent-actions`
- `POST /api/workflows/{id}/agent-actions/{event_id}/approve`
- `POST /api/workflows/{id}/agent-actions/{event_id}/reject`
- `POST /api/workflows/{id}/agent/query`

### Initial Allowlisted Agent Action

`stage_retraining_from_corrections`

Approval requirements:

- A `corrected_mask_path`, `written_path`, existing workflow `corrected_mask_path`, or latest `proofreading.masks_exported` event artifact must exist.
- Approval updates workflow stage to `retraining_staged`.
- Approval logs `agent.proposal_approved` and `retraining.staged`.
- Approval returns client effects:
  - `navigate_to: "training"`
  - `set_training_label_path: corrected_mask_path`

## Frontend

### Context

`WorkflowProvider` loads `GET /api/workflows/current` on startup and exposes:

- `workflow`
- `events`
- `refreshWorkflow`
- `refreshEvents`
- `updateWorkflow`
- `appendEvent`
- `proposeAgentAction`
- `approveAgentAction`
- `rejectAgentAction`
- `queryAgent`
- `lastClientEffects`
- `consumeClientEffects`

### Timeline

`WorkflowTimeline` displays the current workflow stage and latest events. Pending `agent.proposal_created` events expose Approve and Reject controls.

### Module Wiring

- Visualization passes `workflow_id` to `/neuroglancer`.
- Inference passes `workflow_id` to `/start_model_inference` and logs terminal completion/failure from polling.
- Training passes `workflow_id` to `/start_model_training`.
- Mask Proofreading renders EHTool and passes active `workflow_id`.
- EHTool dataset load sends `workflow_id` to `/eh/detection/load`.
- EHTool export records latest corrected mask path and exposes "Stage for retraining."

## Tests

Backend coverage:

- Workflow creation/current behavior.
- Workflow patch, event append, and event list.
- Agent proposal approve/reject flow.
- EHTool load/classify/save/export workflow event linkage.

Frontend coverage:

- Mask Proofreading renders EHTool with workflow id.
- Workflow timeline renders events and approve/reject buttons.
- Workflow provider loads current workflow and applies approval client effects.

## Known Limits

- No Alembic migration yet; SQLite compatibility uses `create_all` plus a narrow column patch for `ehtool_sessions.workflow_id`.
- No model-version artifact table yet.
- No evaluation/comparison artifact yet.
- The workflow-aware agent is deterministic fallback logic, not a full LLM planner.
- Inference completion/failure logging depends on frontend polling observing terminal status.
