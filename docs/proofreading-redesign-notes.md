# Proofreading Redesign Notes

Updated: 2026-04-25

## Log Findings From Latest Run

- The largest runtime defect was not Electron rendering. The app log showed
  `proofreading_instance_filmstrip_served` for `kind=mask_all`, `axis=xy`,
  `z_start=48`, `z_count=12`, `max_dim=384` taking `25774.6 ms`, with nearly
  all time reported inside the resize/render path.
- The root cause was `labels_to_rgba` assigning colors by looping over every
  unique label and then scanning the full slice for each label. On dense
  connectomics labels, this turns all-label overlays into a pathological
  `unique_labels x pixels` operation.
- Mask save itself completed and wrote an artifact:
  `/Users/adamg/seg.bio/testing_data/snemi/seg/.pytc_instance_labels.tif`.
  The save request took about `946 ms`, changed 86 pixels, and recorded 2622
  blocked pixels.
- `/app/log-event` request bookkeeping was flooding the JSONL app log. Keeping
  client events is useful; duplicating every client-log POST start/finish is
  not. The middleware should suppress normal bookkeeping for that endpoint while
  still logging slow or failed log submissions.

## SOTA UI/Workflow Takeaways

- CAVE frames connectomics proofreading as collaborative, versioned,
  time-travelable annotation infrastructure rather than a static post-hoc edit
  tool. Prototype implication: save/export state must be explicit and visible,
  not hidden behind a transient canvas. Source:
  https://www.nature.com/articles/s41592-024-02426-z
- CAVEclient describes CAVE as microservices for versioning connectomics data,
  annotations, metadata, and segmentations. Prototype implication: our local
  app should model persistent artifacts, corrections, and review decisions as
  first-class records even before becoming CAVE-scale. Source:
  https://www.caveconnecto.me/CAVEclient/
- WEBKNOSSOS presents the expected connectomics flow as upload, preprocessing,
  collaborative annotation, data management, segmentation, proofreading, and
  connectome viewing. Prototype implication: the proofreading screen should make
  queue, canvas, review decision, and export/persistence adjacent. Source:
  https://home.webknossos.org/use-cases/connectomics
- Neuroglancer is the reference WebGL volumetric viewer, with an ecosystem
  around precomputed format, CloudVolume, TensorStore, meshes, and scalable
  downsampling. Prototype implication: PyTC Client should avoid pretending a
  React canvas can become a petascale viewer; instead, optimize the local editor
  and leave a clear future path to Neuroglancer-compatible data services.
  Source: https://github.com/google/neuroglancer
- Guided proofreading work identifies visual search as a bottleneck and treats
  proofreading as correcting split/merge errors while generating training data.
  Prototype implication: a review queue and fast slice navigation matter more
  than generic file-browser controls inside proofreading. Source:
  https://openaccess.thecvf.com/content_cvpr_2018/papers/Haehn_Guided_Proofreading_of_CVPR_2018_paper.pdf
- MONAI Label treats annotation as an AI-assisted service with active learning,
  3D Slicer/OHIF frontends, and incremental model improvement. Prototype
  implication: the right product loop is annotate/proofread, persist, retrain,
  evaluate, then pick the next useful sample or region. Source:
  https://www.sciencedirect.com/science/article/pii/S1361841524001324
- Human-AI interaction guidance emphasizes conveying local uncertainty and
  setting expectations at the instance level. Prototype implication: agent and
  UI language should be short, local, and action-oriented, with uncertainty
  exposed near the item being reviewed. Source:
  https://www.microsoft.com/en-us/research/articles/how-to-build-effective-human-ai-interaction-considerations-for-machine-learning-and-software-engineering/
- micro-SAM shows current microscopy annotation tools moving toward interactive
  2D/3D segmentation and tracking through napari. Prototype implication:
  prompt-based correction is a good later feature, but the current priority is a
  reliable edit/save/export loop. Source:
  https://github.com/computational-cell-analytics/micro-sam

## Current Redesign Decisions

- Replace drawer/collapse navigation with a stable workbench:
  review queue left, editor center, current action/save/export panel right.
- Keep case-study/researcher controls out of the participant proofreading UI.
- Treat "save mask" as a persistence operation with visible artifact/export
  state, not just a canvas action.
- Use fast image-only previews during aggressive slider scrubbing, then fetch
  richer overlays only when the slice is committed or the UI is idle.
- Vectorize label-to-color rendering so all-label context overlays are not
  catastrophically slow on real segmentation volumes.
- Keep app-event logging dense around real proofreading actions, but avoid
  self-noise from logging the log endpoint itself.

## 2026-04-25 Canvas-First UI Reset

- The screenshot from the Mito25 smoke project showed the workbench becoming a
  nested form UI instead of a proofreading viewer: large header card, separate
  slice rail, duplicate embedded layer toolbar, left queue, right action panel,
  and a small canvas boxed inside all of it.
- The redesign now treats the central image as the primary object. Review
  decisions, axis selection, active instance metadata, mask readiness, and export
  access sit in the viewer header.
- The slice scrubber remains crucial, but it is now attached to the viewer
  surface as a bottom dimension control with tick marks and a visible current
  slice label. The always-open black tooltip was removed because it visually
  fought the image.
- The embedded editor's own layer toolbar is hidden in workbench mode so there
  is one slice-navigation source of truth.
- The queue no longer shows a redundant "Load dataset" button during an active
  session. Dataset switching is promoted to the workbench header instead.
- The right panel is now secondary "Details" material: active object, saved
  output, opacity controls, and export/staging. It should not carry the main
  review decision loop.
- A follow-up compression fix made the canvas fit the available stage and
  clamps zoom/pan so the image cannot collapse into a tiny off-canvas thumbnail
  after resizing or scrolling. The queue also collapses sooner on narrower
  windows.
- Research rationale and source links are recorded in
  `docs/research/agentic-ui-design-pass.md`.

## Remaining Follow-Up

- Add a tile/chunk-backed viewer path for large volumes instead of repeatedly
  encoding full PNG slices.
- Add explicit split/merge proofreading tools; current paint/erase is only a
  useful local correction primitive.
- Add a hotspot/review queue populated by model uncertainty and error evidence,
  not just instance IDs.
- Add export adapters for OME-Zarr/NGFF and Neuroglancer precomputed when moving
  beyond the local TIFF prototype.
- Add browser-level manual tests that measure scrub latency, save latency, and
  artifact persistence on the Mito25 and SNEMI sample projects.

## 2026-04-25 Agent-Orchestrated Proofreading Entry

- The global agent can now emit a `start_proofreading` runtime action with
  image, mask, and review-name overrides. The proofreading tab consumes that
  action and calls the same loader endpoint used by the manual form.
- The loader language now starts from "What should I proofread?" and offers a
  one-click "Start proofreading this pair" path for detected image/mask pairs.
- The active workbench uses "Change data", "Focus view", "Review details",
  "Saved edits", and "Use edits for training" so the screen reads like an
  editing task rather than backend provenance management.
