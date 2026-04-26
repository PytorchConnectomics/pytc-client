# Agentic UI Design Pass

Updated: 2026-04-25

## Scope

This note records the design pass behind the mask proofreading reset. The goal
is not to make PyTC Client look like a generic AI chat app. The goal is to make
the biologist-facing workflow behave like a scientific image viewer with bounded
agent assistance layered around the work, not competing with it.

## Sources Checked

- Microsoft Guidelines for Human-AI Interaction:
  https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/2025-1-31/
- Magentic-UI human-in-the-loop agentic systems:
  https://arxiv.org/abs/2507.22358
- WEBKNOSSOS proofreading workflows:
  https://docs.webknossos.org/webknossos/proofreading/index.html
- WEBKNOSSOS connectomics workflow positioning:
  https://home.webknossos.org/use-cases/connectomics
- Neuroglancer/PyTorch Connectomics viewer integration notes:
  https://connectomics.readthedocs.io/en/latest/external/neuroglancer.html
- 3D Slicer Segment Editor:
  https://slicer.readthedocs.io/en/5.8/user_guide/modules/segmenteditor.html
- napari viewer layout and dimension slider pattern:
  https://napari.org/stable/tutorials/fundamentals/viewer.html
- Nature 2025 connectomic reconstruction manual proofreading workflow:
  https://www.nature.com/articles/s41586-025-08985-1

## Design Principles For This App

- Canvas first. The active image/mask view is the work object; controls should
  orbit it rather than push it into a small nested card.
- One navigation source of truth. A volume viewer should not show duplicate
  layer headers, duplicate slice controls, and duplicate next/previous controls
  in competing places.
- Keep state local to the action. The current slice, active instance, edit
  readiness, save state, and review decision should be visible next to the
  canvas, not hidden in a generic side panel.
- Use progressive disclosure. Export paths, provenance details, and staging
  controls matter, but they are secondary to inspect/edit/review/save.
- Preserve expert imaging patterns. napari and Slicer both keep slice navigation
  tightly coupled to the image view; Slicer also treats keyboard-driven slice
  movement and tool switching as core editing affordances.
- Bound agent behavior. Agent help should surface short, local suggestions and
  never obscure the segmentation canvas or overload the user with long prose.
- Avoid case-study-specific participant UI. Study instrumentation belongs in
  logs/research exports, not as participant-facing controls in the prototype.

## Current Proofreading UI Reset Decisions

- Replace the heavy top card with a compact workbench header.
- Keep the left review queue, but remove the redundant "Load dataset" action
  from inside the active proofreading queue.
- Move review decisions into the viewer header so the user can inspect and
  classify without moving attention to a separate panel.
- Hide the embedded editor's duplicate layer toolbar when used inside the
  proofreading workbench.
- Attach the slice slider directly to the viewer surface and keep tick marks and
  an explicit current-slice label.
- Keep export, overlay opacity, and artifact paths in a narrower details panel
  rather than making them the primary workflow.

## Remaining UI/Agent Work

- Agent messages need a short "biologist skim" format: conclusion first,
  1-3 bullets, explicit action or no action.
- File/project mounting needs a separate flow redesign. The current path-based
  mounting flow is still too manual and error-prone.
- The editor still needs a more complete split/merge-oriented tool model; paint
  and erase are local correction primitives, not connectomics-grade proofreading.
- The canvas should eventually move toward tiled/chunked rendering for large
  volumes rather than repeated full-slice PNG transfer.

## 2026-04-25 Product-Language/Orchestrator Update

- The UI problem is broader than density: the app was exposing research/backend
  bookkeeping ("evidence", "artifacts", "candidate", "correction set") where a
  biologist expects task language ("previous result", "new result", "your
  edits", "reference mask").
- The agent strip should be a workflow orchestrator, not a second dashboard.
  It now emphasizes one next action plus a small status drawer; readiness counts
  and path details should not compete with the user's image/mask task.
- "Proofread this data" is now an executable client effect, not just navigation:
  the backend emits a `start_proofreading` runtime action and the frontend loads
  the current image/mask pair into the proofreading workbench when available.
- Advanced metric dataset/channel fields are hidden behind "Metric options".
  This follows progressive disclosure: common user action first, technical
  disambiguation only when HDF5/channel details are required.
- Remaining design debt: turn the whole app into an intent ladder
  (`choose data -> run model -> proofread -> train on edits -> compare`) rather
  than separate modules that happen to share workflow state.
