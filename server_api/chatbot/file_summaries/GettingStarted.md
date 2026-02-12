# Getting Started with PyTC Client

PyTC Client (PyTorch Connectomics Client) is a desktop application for biomedical image segmentation. It provides tools for managing files, visualizing data in Neuroglancer, training and running inference with deep learning models, proofreading synapse annotations, and detecting errors in image stacks.

## Launching the Application

When you first open PyTC Client, a **Change Views** dialog appears. This lets you choose which workflow tabs to enable. The available workflows are:

- **File Management** — Browse, upload, and organize files on the server
- **Visualization** — View image and label data in Neuroglancer
- **Model Training** — Configure and launch training jobs
- **Model Inference** — Run inference with trained models
- **Tensorboard** — Monitor training metrics in real time
- **SynAnno** — Proofread synapse annotations
- **Worm Error Handling** — Detect and classify errors in worm image stacks

Check the workflows you want, then click **Launch Selected**. You can change your selection later by clicking **Change Views** in the top navigation bar.

## Application Layout

The application has three main areas:

1. **Top Navigation Bar** — Displays the PyTC logo, application title, and a row of tabs for each enabled workflow. Click a tab to switch between pages. The bar also includes a **Change Views** button and an **AI Chat** toggle button.

2. **Main Content Area** — Shows the currently selected workflow page (e.g., File Manager, Visualization, Model Training).

3. **AI Chat Drawer** — A collapsible panel on the right side of the screen. Click the **AI Chat** button in the top bar to open or close it. You can drag the left edge of the chat drawer to resize it. Use the chat to ask questions about the application, get help with workflows, or request training/inference commands.

## Using the AI Chat

The chat panel appears as a sliding drawer on the right. To use it:

1. Click the **AI Chat** button in the top navigation bar to open the drawer.
2. Type your question in the text input at the bottom and press **Enter** or click **Send**.
3. The assistant will respond with guidance based on the application's documentation.
4. Click **Clear Chat** to start a new conversation.

The chat supports markdown formatting, including tables, code blocks, and lists.

## Keyboard Shortcuts (Global)

These standard editing shortcuts work throughout the application:

| Shortcut    | Action     |
| ----------- | ---------- |
| Cmd+C       | Copy       |
| Cmd+V       | Paste      |
| Cmd+X       | Cut        |
| Cmd+A       | Select All |
| Cmd+Z       | Undo       |
| Cmd+Shift+Z | Redo       |
