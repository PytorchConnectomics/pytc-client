# Model Inference

The normal workflow is: choose the image volume, choose a checkpoint, choose an
output folder, then let the assistant start inference after approval. The
assistant should infer the closest safe config from project state when possible
and should not ask a biologist to tune inference internals by default.

Visible user-facing fields:

- **Input image** is the volume to segment.
- **Checkpoint** is the trained model file.
- **Output folder** is where the prediction is written.
- **Start Inference** launches the approved run.

Advanced options such as batch size, test-time augmentation, stride, blending,
chunking, eval mode, and raw YAML are for explicit override or debugging. If the
user simply wants a volume segmented, prefer a run-ready action over an
explanation of these controls.

Runtime logs should be summarized as plain status: idle, running, completed,
failed, or needs attention. Show raw terminal output only when the user asks or
when troubleshooting a failure.
