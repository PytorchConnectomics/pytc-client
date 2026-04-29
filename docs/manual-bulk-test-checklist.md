# Manual Bulk Test Checklist

Use this after large prototype checkpoints when you want to verify the current
TOCHI-facing workflow without running full PyTC training.

## Startup

- From `/Users/adamg/seg.bio/pytc-client`, run `scripts/start.sh`.
- Confirm Electron opens and all three backend services report ready.
- Ignore `.zshrc` `pyenv` warnings for this app unless they block Python.

## File Management

- Open File Management.
- Confirm the suggested smoke project card appears.
- Confirm it reports image, label, prediction, config, and checkpoint roles.
- Click `Mount Test Project` or `Open Test Project`.
- Confirm `mito25-paper-loop-smoke` opens without manual path browsing.
- Confirm `data/image`, `data/seg`, `configs`, `checkpoints`, and `predictions`
  are present.
- Ask the assistant `what should I do next?` after mounting.
- Confirm the workflow no longer behaves like no data is mounted: it should
  recommend inference/visualization instead of asking you to mount data.
- Right-click the mounted root and confirm `Unmount Project` is available.

## File Selection

- In Train Model or Run Model, click the folder icon inside a path field and confirm the
  file picker opens.
- Click a folder row/name to navigate into it.
- Use `Use folder` or `Select Current Directory` when the folder itself is the
  intended input/output.
- Confirm manual path typing still works, but does not feel like the primary
  file-selection path.

## Evidence Panel

- Open the assistant drawer and click `Status`.
- Confirm the assistant drawer opens with workflow context visible.
- Open Tensorboard/Monitoring.
- Confirm `Review status` is visible.
- Confirm the `Loop progress` map is visible.
- Confirm the panel shows the next incomplete gate if the loop is not complete.
- Confirm previous result, new result, your saved edits, and reference-mask rows
  use short user-facing labels.
- Confirm `Compare results` is disabled with a useful missing-input message when
  previous result, new result, or reference mask paths are absent.
- Click `Metric options` only when dataset keys/channels need manual override.

## Metric Computation

- For HDF5/PyTC outputs, enter dataset key `vol0` for baseline/candidate.
- Use channel `0` for PyTC `result_xy.h5` probability maps when applicable.
- Use ground-truth dataset `data` for the curated mito25 segmentation file.
- Click `Compare results` only after previous-result, new-result, and reference paths are
  recorded in workflow evidence.
- Confirm metric deltas render for Dice, IoU, and voxel accuracy.
- Confirm the latest comparison report path appears.

## Bundle Export

- Click `Export report`.
- Confirm the UI reports file/run/comparison counts and missing path count.
- Refresh evidence or open the workflow timeline/context panel.
- Confirm a `workflow.bundle_exported` event exists.

## Proofreading Provenance

- Open Mask Proofreading on a small loaded volume.
- Confirm the editor exposes a visible `Save mask` control, not only a keyboard
  shortcut.
- Paint or erase a small region and confirm an `unsaved edits` indicator appears.
- Save at least two mask edits in distinct instances/regions.
- Export masks.
- Confirm the workflow evidence panel shows a corrected-mask path.
- Confirm the correction set reports nonzero edits and regions once evidence is
  refreshed.

## Agent Controls

- Ask the assistant: `what should I do next?`
- Confirm the reply uses a compact `Do this` / `Why` / `Ready` style rather than
  a long explanation.
- Ask the assistant gibberish such as `mmajkf,ansdjs`.
- Confirm it does not produce workflow action cards for that gibberish.
- From inference stage with no prediction output, ask for the next step and
  confirm the assistant action card is `Run model`.
- From a mounted project with an image/mask pair, click `Proofread this data`
  and confirm the app opens Proofread and starts loading that pair without
  manual path entry.
- From proofreading after a mask export, ask for the next step and confirm the
  assistant action card is `Use edits for training`.
- Click `Use edits for training` and confirm a pending agent proposal appears
  in workflow context/timeline instead of silently staging retraining.
- Approve the proposal and confirm the workflow moves to `retraining_staged` and
  the corrected-mask path is loaded into training labels.

## Known Boundaries

- This checklist does not prove full training quality.
- This checklist does not prove long-running cancellation/retry/recovery.
- This checklist does not prove browser-level proofreading at scale.
- A paper-ready case-study loop still needs a fresh app-launched baseline
  inference, correction export, retraining/fine-tuning, candidate inference, and
  before/after evaluation over those fresh outputs.
