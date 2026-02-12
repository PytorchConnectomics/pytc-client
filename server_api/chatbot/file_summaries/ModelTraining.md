# Model Training Page

The Model Training page lets you configure and launch deep learning training jobs for biomedical image segmentation using PyTorch Connectomics. Setup follows a guided 3-step process, after which you can start and monitor your training run.

## 3-Step Configuration Wizard

The configuration wizard (stepper) walks you through three steps. You must complete each step before advancing to the next. Click **Next** to advance and **Previous** to go back.

### Step 1: Set Inputs

Specify the file paths for your training data:

- **Input Image** — Path to your training image data (file or directory on the server). Click the folder icon to browse, type a path, or drag and drop.
- **Input Label** — Path to the corresponding ground-truth labels.
- **Output Path** — Directory where training outputs (checkpoints, logs) will be saved.
- **Log Path** — Directory for training logs (used by TensorBoard for monitoring).

All four fields are required before you can proceed. The application will show a warning listing any missing fields if you try to advance without filling them in.

### Step 2: Base Configuration

Choose a starting YAML configuration file for your training job:

- **Upload YAML File** — Click the **Upload YAML File** button to upload a configuration file from your local machine.
- **Choose a preset config** — Select from a dropdown of preset configurations available on the server (e.g., `Lucchi-Mitochondria.yaml`, `CREMI-Synapse.yaml`).

Once a config is loaded, you will see:

- **Loaded** indicator showing which file or preset is active. If you modify settings, a **Modified** label appears with a **Revert to preset** link to restore the original values.
- **Effective dataset paths** — A summary box showing the common folder, image name, label name, and output path that will be written into the YAML config.
- **Model architecture** dropdown — Select the neural network architecture (e.g., `unet_super`, `fpn`). The available options are fetched from the server.
- **Sliders** for quick adjustment of common parameters:
  - **Batch size** (1–32)
  - **GPUs** (0–8)
  - **CPUs** (1–16)

### Step 3: Advanced Configuration

Fine-tune detailed training parameters using structured controls organized into sections:

**Common training knobs:**

- Optimizer (SGD, Adam, AdamW)
- LR scheduler (MultiStepLR, CosineAnnealingLR, StepLR)
- Learning rate
- Batch size
- Total iterations
- Save interval (how often to save checkpoints)
- Validation interval

**System:**

- Distributed training (on/off)
- Parallel mode (DP or DDP)
- Debug mode (on/off)

**Model:**

- Block type (residual, plain)
- Backbone (resnet, repvgg, botnet)
- Normalization (bn, sync_bn, in, gn, none)
- Activation (relu, elu, leaky)
- Pooling layer (on/off)
- Mixed precision (on/off)
- Aux output (on/off)

**Dataset:**

- 2D dataset (on/off)
- Load 2D slices (on/off)
- Isotropic data (on/off)
- Drop channels (on/off)
- Reduce labels (on/off)
- Ensure min size (on/off)
- Pad mode (reflect, constant, symmetric)

**Solver (advanced):**

- Weight decay
- Momentum
- Clip gradients (on/off)
- Clip value

Each setting is displayed as a dropdown, number input, or toggle switch.

**Open raw YAML** — Click this button at the bottom to open a full-screen YAML text editor modal where you can directly edit the raw YAML configuration. The modal includes a **Format YAML** button to auto-format the text and a **Copy** button to copy the YAML to your clipboard. If there is a syntax error, a red warning appears.

When finished, click **Done** to save the configuration.

## Starting and Stopping Training

After completing the 3-step wizard:

1. Click **Start Training** to launch the training job on the server.
2. The page displays the current training status (e.g., "Training in progress…").
3. Click **Stop Training** at any time to terminate the running job.

The training status is polled automatically so you can see updates without refreshing. You can switch to the **Tensorboard** tab to monitor training metrics like loss curves in real time.
