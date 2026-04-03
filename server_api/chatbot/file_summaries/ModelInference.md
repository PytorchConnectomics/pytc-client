# Model Inference Page

The Model Inference page lets you run inference (prediction) using a trained segmentation model. It uses the same 3-step configuration wizard as Model Training, with slight differences in the required inputs and available settings.

## 3-Step Configuration Wizard

### Step 1: Set Inputs

Specify the file paths for your inference data:

- **Input Image** — Path to the image data you want to run inference on (file or directory on the server). Click the folder icon to browse, type a path, or drag and drop. You can also click the **?** button next to the field for AI-powered help.
- **Output Path** — Directory where inference results will be saved.
- **Checkpoint Path** — Path to the trained model checkpoint file (e.g., `/path/to/checkpoint_100000.pth.tar`). This is the model that will be used for prediction.

All three fields are required before you can proceed.

### Step 2: Base Configuration

Choose a YAML configuration file, just like in training:

- **Upload YAML File** — Upload a config from your local machine.
- **Choose a preset config** — Select a preset from the server dropdown.

Once loaded, you will see:

- **Loaded** indicator and **Revert to preset** option (if modified).
- **Effective dataset paths** summary.
- **Model architecture** dropdown.
- **Sliders** for quick parameter adjustment:
  - **Batch size** (1–32)
  - **Augmentations** (1–16) — Number of test-time augmentations to average over.

### Step 3: Advanced Configuration

Fine-tune inference-specific parameters:

**Common inference knobs:**

- Batch size
- Augmentations (AUG_NUM)
- Blending mode (gaussian or constant)
- Eval mode (on/off — whether to compute evaluation metrics)

**Inference (advanced):**

- Run singly (process volumes one at a time)
- Unpad output (remove padding from output)
- Augment mode (mean or max — how to combine augmented predictions)
- Test count (number of test volumes)

Each setting is displayed as a dropdown, number input, or toggle switch.

**Open raw YAML** — Opens a full-screen YAML text editor modal for direct editing. Includes **Format YAML** and **Copy** buttons.

Click **Done** to save the configuration.

## Starting and Stopping Inference

After completing the wizard:

1. Click **Start Inference** to launch the inference job on the server.
2. The page shows the current inference status.
3. Click **Stop Inference** at any time to terminate the job.

The inference status is polled automatically so you can monitor progress without refreshing.
