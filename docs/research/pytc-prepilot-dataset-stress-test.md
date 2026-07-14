# PyTC Dataset Prepilot Stress Test

Date: 2026-04-28

## Goal

Run a solo prepilot before external case studies to find where the prototype breaks on realistic PyTorch Connectomics (PyTC) workflows: project setup, role inference, config selection, training/inference launch, proofreading, correction export, retraining, candidate inference, metrics, and evidence export.

The important constraint is that most public PyTC datasets provide data and configs, but not always matching pretrained checkpoints. For a credible stress test, treat "baseline inference" as one of:

- Use an existing local checkpoint if available.
- Run a short training/fine-tuning pass first, then infer from that checkpoint.
- Use a published upstream checkpoint only when the checkpoint source, config family, and expected tensor outputs match.

## Source Grounding

- PyTC paper: PyTC is a framework for semantic and instance segmentation of volumetric microscopy data, with benchmark claims across CREMI, MitoEM, and NucMM. Source: [PyTorch Connectomics paper](https://arxiv.org/abs/2112.05754).
- PyTC docs: The official tutorials map specific config families to Lucchi, MitoEM, SNEMI3D, and CREMI workflows. Sources: [mitochondria tutorial](https://connectomics.readthedocs.io/en/latest/tutorials/mito.html), [neuron tutorial](https://connectomics.readthedocs.io/en/latest/tutorials/neuron.html), [synapse tutorial](https://pytorch-connectomics.readthedocs.io/en/latest/tutorials/synapse.html).
- Upstream PyTC has moved toward a v2.0 stack with PyTorch Lightning, MONAI, Hydra/OmegaConf, pretrained tutorial checkpoints, and `just` workflows. This is useful precedent, but the current client is wired around the older `scripts/main.py` + YAML configs. Source: [current PyTC GitHub](https://github.com/PytorchConnectomics/pytorch_connectomics).

## Recommended Dataset Ladder

Run the ladder in order. Stop when the prototype fails; log the failure as product evidence rather than forcing the demo through.

| Tier | Dataset | Why this tier matters | Data source | Existing local config(s) | Expected stress point |
| --- | --- | --- | --- | --- | --- |
| 0 | Local Mito25 / Mito25 smoke | Fastest app-level closed-loop rehearsal using the app's current demo path | Existing local data under `/Users/adamg/seg.bio/testing_data/mito25` when mounted | `configs/MitoEM/Mito25-Local-Smoke-BC.yaml`, `configs/MitoEM/Mito25-Local-BC.yaml` | End-to-end app state, project setup, proofreading save/export, short training/inference job handling |
| 1 | MitoEM toy crop | Real PyTC/Hugging Face data, small enough to iterate | [pytc/MitoEM](https://huggingface.co/datasets/pytc/MitoEM/tree/main), especially `mitoem_R_train_4um_im.h5` and `mitoem_R_train_4um_seg.h5` | Adapt `configs/MitoEM/Mito25-Local-BC.yaml` for direct HDF5 crop, or `MitoEM-R-Base.yaml` + `MitoEM-R-BC.yaml` for full tiled data | HDF5 role inference, small real mitochondria proofreading, model-run artifact lineage |
| 2 | Lucchi / Lucchi++ | Small classic mitochondria semantic segmentation benchmark with public labels | PyTC docs link `lucchi.zip`; also [pytc/tutorial](https://huggingface.co/datasets/pytc/tutorial/tree/main) has `lucchi++.zip`; background at [Connectomics Lucchi++](https://sites.google.com/view/connectomics) | `configs/Lucchi-Mitochondria.yaml` | TIFF stack handling, semantic rather than instance masks, local evaluation with IoU/F1-style metrics |
| 3 | CREMI synaptic clefts | Multi-volume HDF5 benchmark and synapse task; tests non-mito biology | [CREMI data page](https://cremi.org/data/) cropped A/B/C volumes or [pytc/tutorial](https://huggingface.co/datasets/pytc/tutorial/tree/main) `cremi.zip` | `configs/CREMI/CREMI-Base.yaml` + `configs/CREMI/CREMI-Foreground-UNet.yaml` | Multiple image/label pairs, `@`-separated config paths, HDF5 internal dataset keys, synapse-specific metrics |
| 4 | SNEMI3D neurons | Classic dense neurite segmentation with affinity output and postprocessing | PyTC docs `snemi.zip`; challenge context at [SNEMI3D](https://snemi3d.grand-challenge.org/) | `configs/SNEMI/SNEMI-Base.yaml` + `configs/SNEMI/SNEMI-Affinity-UNet.yaml` | Affinity maps are not directly editable instance masks; requires waterz/zwatershed postprocessing before proofreading |
| 5 | NucMM | Non-mito, non-synapse nuclei; tests modality generality and project agnosticism | [NucMM project page](https://pytorchconnectomics.github.io/datasets/proj/nucmm/) and [pytc/NucMM](https://huggingface.co/datasets/pytc/NucMM/tree/main) | `configs/NucMM/NucMM-Mouse-Base.yaml` + `NucMM-Mouse-UNet-BC.yaml`; `NucMM-Zebrafish-Base.yaml` + `NucMM-Zebrafish-UNet-BC.yaml` | Large-volume nuclei, EM vs micro-CT modality mismatch, non-mito proofreading language |
| Stretch | JWR15 synapse polarity | Tests arbitrary-volume synapse inference and semantic synapse masks | PyTC synapse docs mention `jwr15_synapse.zip` | `configs/JWR15/synapse/JWR15-Synapse-Base.yaml` + `JWR15-Synapse-BCE.yaml` | Pretrained-checkpoint availability, arbitrary-volume inference, non-instance semantic masks |
| Stretch | MitoEM2.0 | Current PyTC dataset ecosystem and larger modern mitochondrial scope | [pytc/MitoEM2.0](https://huggingface.co/datasets/pytc/MitoEM2.0/tree/main) | No matching local legacy config yet; evaluate separately | 17GB scale, new dataset organization, likely requires schema/config adaptation |

## Project Folder Schema For The Prepilot

For every dataset, stage a project folder under a consistent schema before opening it in the client:

```text
testing_projects/prepilot_<dataset_slug>/
  data/
    image/
    seg/
    prediction/
  configs/
  checkpoints/
  outputs/
  notes/
    prepilot-log.md
```

Minimum workable project:

- `data/image`: one image volume, image stack folder, or PyTC JSON/txt list.
- `data/seg`: optional label/mask volume or stack.
- `configs`: the PyTC config copied from `pytorch_connectomics/configs/...` with local paths patched or overridden by the app.
- `checkpoints`: optional. If empty, the prepilot starts with a short training run.
- `outputs`: runtime artifacts, predictions, checkpoints, exported masks, metrics, and evidence bundle.

The app should infer roles, but the user must explicitly confirm the role mapping before workflow state mutates.

## Solo Prepilot Script

### Pass A: Fast App Loop On Local Mito25

Use this to confirm the app loop before spending time on external data.

1. Reset app workflow state and mount only the local Mito25 project.
2. Confirm image, label/mask, config, output path, and checkpoint roles.
3. Ask the agent: "What should I do next?"
4. Expected agent behavior: it should propose a concrete workflow action, not dump config docs.
5. Run short baseline inference if a checkpoint exists; otherwise run the smoke training config first.
6. Open proofreading, inspect 3 objects, mark at least one `needs fix`, draw/edit, save mask.
7. Export corrected masks.
8. Stage retraining from corrections.
9. Run short candidate inference.
10. Compute before/after metrics.
11. Export the evidence bundle.

Pass conditions:

- Role confirmation is explicit and editable.
- Agent can open or propose the next app action with approval.
- Proofreading save persists to both app state and artifact path.
- Exported correction is visible to retraining.
- Metrics compare baseline vs candidate, even if the model is intentionally weak.
- Evidence bundle contains events, configs, paths, masks/predictions, metric report, and run summaries.

### Pass B: MitoEM Toy Crop

Use this to test project agnosticism while staying small.

1. Download `mitoem_R_train_4um_im.h5` and `mitoem_R_train_4um_seg.h5` from [pytc/MitoEM](https://huggingface.co/datasets/pytc/MitoEM/tree/main).
2. Stage them as `data/image/..._im.h5` and `data/seg/..._seg.h5`.
3. Copy `configs/MitoEM/Mito25-Local-BC.yaml` into the project config folder and patch only paths/output names.
4. Start from blank app state and mount the project folder.
5. Confirm roles and verify the app does not silently fall back to local mito25 defaults.
6. Run the same loop as Pass A, but record every place the UI assumes "mito25".

Expected findings:

- The role profiler should detect `_im.h5` as image and `_seg.h5` as label.
- The proofreader should load slices without manual HDF5-key entry if the file has a simple volume dataset.
- If HDF5 keys are ambiguous, the app should ask for a key rather than fail silently.

### Pass C: Lucchi / Lucchi++

Use this to stress format generality and semantic segmentation.

1. Download `lucchi.zip` from the PyTC tutorial source or `lucchi++.zip` from [pytc/tutorial](https://huggingface.co/datasets/pytc/tutorial/tree/main).
2. Arrange files to match `configs/Lucchi-Mitochondria.yaml`: `img/train_im.tif`, `label/train_label.tif`, `img/test_im.tif`.
3. Mount the project and confirm roles.
4. Ask the agent to set up the run for "mitochondria semantic segmentation on Lucchi".
5. Run a very short training smoke, then inference.
6. Compute semantic metrics against public labels where available.

Expected findings:

- The app should not force an instance-proofreading mental model onto semantic masks.
- The agent should mention "semantic mitochondria mask" and "threshold/IoU" rather than "instance proofreading queue" unless instance labels are present.
- Runtime summaries should show training status and useful warnings, not raw terminal logs by default.

### Pass D: CREMI

Use this to test multi-volume HDF5 and synapse-specific workflows.

1. Download cropped CREMI A/B/C data from [CREMI](https://cremi.org/data/) or use the PyTC tutorial `cremi.zip`.
2. Arrange expected paths for `CREMI-Base.yaml`, or patch config paths:
   - training images: `corrected/im_A.h5@corrected/im_B.h5@corrected/im_C.h5`
   - training labels: `corrected/syn_A.h5@corrected/syn_B.h5@corrected/syn_C.h5`
   - inference images: `corrected/im_A+.h5@corrected/im_B+.h5@corrected/im_C+.h5`
3. Mount project folder.
4. Confirm multiple image/label pairs rather than a single pair.
5. Ask the agent: "Prepare a synaptic cleft detection run."
6. Observe whether the agent can identify missing label paths, HDF5 keys, and config mismatch before starting.

Expected findings:

- Current project role schema may be too single-pair oriented.
- The app likely needs first-class support for batches/pair tables.
- Proofreading may need a synapse-specific review mode rather than object-instance review.

### Pass E: SNEMI3D

Use this only after the app can handle CREMI/MitoEM cleanly.

1. Download SNEMI data using the PyTC neuron tutorial source.
2. Arrange `image/train-input.tif`, `seg/train-labels.tif`, and `test-input.tif`.
3. Use `SNEMI-Base.yaml` + `SNEMI-Affinity-UNet.yaml`.
4. Ask the agent to set up neuron affinity segmentation.
5. Verify the agent explains that raw model output is an affinity map and needs waterz/zwatershed before it becomes an editable segmentation.

Expected findings:

- This will expose whether the prototype incorrectly assumes model outputs are always direct masks.
- A robust agent should route the user through postprocessing and not send affinity channels directly into the proofreader.

### Pass F: NucMM

Use this as the "not connectomics mitochondria" generality test.

1. Download `NucMM-M.zip` or `NucMM-Z.zip` from [pytc/NucMM](https://huggingface.co/datasets/pytc/NucMM/tree/main).
2. Pick one smaller/cropped subset if the zip is too large for an initial run.
3. Use the matching `NucMM-*` base and `UNet-BC` config.
4. Mount and confirm roles.
5. Ask the agent to describe the biological object and run strategy.

Expected findings:

- The agent should adapt language to nuclei segmentation.
- The app should support non-mito instance masks without hardcoded labels, names, or assumptions.
- Large volume I/O and slice navigation will likely surface performance bottlenecks.

## What To Record During The Solo Prepilot

Use a table in `notes/prepilot-log.md` for each dataset:

| Check | Result | Evidence path | Notes |
| --- | --- | --- | --- |
| Project roles inferred correctly | pass/fail | screenshot/log/event id | Was any role wrong or silently defaulted? |
| Config selected correctly | pass/fail | config path | Did app suggest the right PyTC config family? |
| Agent next-step answer useful | pass/fail | chat id | Did it produce action, question, or irrelevant docs? |
| Agent action approval works | pass/fail | event id | Did action mutate app only after approval? |
| Runtime starts | pass/fail | run id | Training/inference job record exists? |
| Runtime summary readable | pass/fail | screenshot | Was raw log hidden unless requested? |
| Proofreading loads quickly | pass/fail | timing | Slice change target: under 1-2s on small crop. |
| Mask save persists | pass/fail | artifact path | Reopen and verify edit remains. |
| Export works | pass/fail | export path | Corrected mask usable by training. |
| Candidate metrics computed | pass/fail | report path | Baseline/candidate/reference all resolved. |
| Evidence bundle exported | pass/fail | bundle path | Includes events, configs, artifacts, metrics. |

## Failure Modes This Prepilot Is Designed To Expose

- The app silently chooses the old mito25 demo project instead of the confirmed project.
- File role inference works for simple HDF5 names but fails for real HDF5 internal datasets.
- Project schema supports one image/mask pair but not multiple pairs or config `@` lists.
- Training/inference jobs start, but the UI exposes terminal logs instead of actionable summaries.
- The agent gives RAG documentation instead of asking/applying workflow-specific decisions.
- The agent treats semantic masks, instance masks, affinity maps, contours, and distance transforms as interchangeable.
- Baseline inference cannot run because checkpoint/config/data tensor shapes are mismatched.
- Proofreading becomes unusable on larger volumes due to slice loading, canvas state, or save/export bugs.
- Metrics only work for the local synthetic path and fail on semantic, affinity, or multi-volume datasets.
- Evidence bundle lacks enough artifact lineage to reconstruct what happened.

## Minimum Prepilot Completion Bar

Before external case studies, the prototype should pass:

1. Local Mito25 closed-loop smoke.
2. MitoEM toy crop project-agnostic setup and proofreading.
3. Lucchi or CREMI non-mito25 setup with at least training/inference launch and a useful agent preflight.

If those pass, the app is ready for a controlled prepilot with another person. If SNEMI3D or NucMM also pass, the system has stronger evidence for project agnosticism.

## Ingested Local Projects

On 2026-04-28, `scripts/ingest_prepilot_datasets.py` staged practical prepilot fixtures under `/Users/adamg/seg.bio/testing_projects`.

| Project | Status | Contents |
| --- | --- | --- |
| `prepilot_mito25_smoke` | ready | Symlinked local Mito25 smoke HDF5 image/seg pairs plus `Mito25-Local-Smoke-BC.yaml`. |
| `prepilot_mitoem_toy` | ready | Downloaded public MitoEM-R 4um HDF5 image/seg crop from Hugging Face and wrote `MitoEM-Toy-BC-Smoke.yaml`. |
| `prepilot_lucchi_pp` | ready | Downloaded/extracted `lucchi++.zip`; staged `train_im.h5`, `train_mito.h5`, `test_im.h5`, and `test_mito.h5` with patched Lucchi config. |
| `prepilot_snemi3d_local` | ready | Symlinked existing local SNEMI train/test TIFFs and labels with patched SNEMI base config plus affinity UNet config. |
| `prepilot_cremi_official` | needs preprocessing | Downloaded official CREMI A/B/C HDF5 containers; manifest records raw and cleft-label HDF5 keys. Legacy PyTC configs expect preprocessed `corrected/im_*.h5` and `corrected/syn_*.h5`, so this fixture intentionally exposes the HDF5-key/config-adaptation gap. |
| `prepilot_nucmm_mouse` | ready | Downloaded/extracted public NucMM-Mouse archive; staged train image/seg HDF5 crops and copied NucMM Mouse configs. |

Each project includes:

- `project_manifest.json` with role paths, source URLs, config paths, and HDF5/TIFF inventories.
- `notes/README.md` with human-readable project guidance.
- `notes/prepilot-log.md` with a pass/fail table for solo testing.

## Paper-Relevant Takeaway

The prepilot should not be framed as "does PyTC achieve SOTA." It should be framed as "does the prototype make an iterative biomedical segmentation loop controllable, inspectable, and recoverable across realistic PyTC datasets?" The strongest TOCHI evidence will be failure localization: where users need agent help, where the workflow is too technical, and where provenance/evidence prevents confusion across long-running segmentation iterations.
