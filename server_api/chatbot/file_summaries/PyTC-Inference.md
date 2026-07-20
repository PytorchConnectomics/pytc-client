# PyTC Inference

PyTorch Connectomics inference creates a prediction mask from an image volume
and a trained checkpoint. In PyTC Client, the assistant should normally hide the
script-level details: infer a safe config from project state, fill input image,
checkpoint, and output path, then ask the user to approve the run.

Command-line form, for debugging or expert use only:

```bash
python scripts/main.py --config-file <config.yaml> --inference --checkpoint <checkpoint.pth.tar>
```

Biologist-facing answer pattern:

- **Do this:** approve the inference run for the current image/checkpoint.
- **Needs:** image volume, checkpoint, output folder.
- **Watch out:** if the job fails, inspect the runtime summary before raw logs.

Advanced controls include patch size, stride, blending, batch size, test-time
augmentation, chunking, and raw YAML overrides. Do not lead with these controls
unless the user asks to override defaults, speed up a run, reduce memory use, or
debug visible artifacts.

Inference outputs are usually HDF5 or TIFF-like prediction volumes. After a run
finishes, the workflow should register the prediction as a model run/artifact so
proofreading and before/after evaluation can use it.
