# Train Model

The normal biologist workflow is not manual YAML tuning. The user should choose
the image/label pair or saved proofreading edits, then ask the assistant to run
training. The assistant should infer a safe preset from the current project,
fill image, label, output, and log paths, apply conservative defaults, and ask
for approval before launching the job.

Use the **Train Model** tab when the user wants to inspect or override what the agent
will run. Keep the visible explanation short:

- **Input image** is the source volume.
- **Input label** is the current mask, corrected mask, or ground truth.
- **Output/log folder** is where checkpoints and run logs are written.
- **Start Training** launches the approved job.

Raw YAML, batch size, CPU/GPU counts, save interval, total iterations, stride,
chunking, and blending are advanced controls. Mention them only if the user
asks to override defaults, debug a failure, or inspect a completed run. Do not
tell a normal biologist to hand-edit these settings as the default path.

Training runtime logs should be treated as diagnostics. The app should summarize
plain states such as idle, running, completed, failed, or needs attention. Show
raw terminal output only on demand or when troubleshooting a failure.
