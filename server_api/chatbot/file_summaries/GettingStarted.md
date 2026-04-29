# Getting Started with PyTC Client

PyTC Client (PyTorch Connectomics Client) is a desktop application for biomedical image segmentation. It provides tools for managing files, visualizing data in Neuroglancer, training and running inference with deep learning models, monitoring experiments, and reviewing image masks.

## Launching the Application

When you first open PyTC Client, the main workflows are available immediately in the top navigation bar:

- **File Management** — Browse, upload, and organize files on the server
- **Visualization** — View image and label data in Neuroglancer
- **Train Model** — Configure and launch training jobs
- **Run Model** — Generate predictions with trained models
- **Tensorboard** — Monitor training metrics in real time
- **Mask Proofreading** — Review and edit mask layers in image stacks

## Application Layout

The application has three main areas:

1. **Top Navigation Bar** — Displays the PyTC logo, application title, and a row of tabs for each workflow. Click a tab to switch between pages. The bar also includes an **AI Chat** toggle button.

2. **Main Content Area** — Shows the currently selected workflow page (e.g., File Manager, Visualization, Train Model).

3. **AI Chat Drawer** — A collapsible panel on the right side of the screen. Click the **AI Chat** button in the top bar to open or close it. You can drag the left edge of the chat drawer to resize it. Use the chat to ask questions about the application, get help with workflows, or request training/inference commands.

## Using the AI Chat

The chat panel appears as a sliding drawer on the right. To use it:

1. Click the **AI Chat** button (message icon) in the top navigation bar to open the drawer.
2. Type your question in the text input at the bottom and press **Enter** or click **Send**.
3. The assistant will respond with guidance based on the application's documentation.

The chat supports markdown formatting, including tables, code blocks, and lists.

### Conversation History

The chat drawer includes a **sidebar** on the left that lists your saved conversations:

- **New chat (+)** — Click the **+** button at the top to start a fresh conversation.
- **Switch conversations** — Click any conversation in the sidebar to load it.
- **Delete a conversation** — Click the trash icon next to a conversation and confirm.
- **Collapse/expand sidebar** — Use the fold/unfold button to hide or show the conversation list.

Conversations are saved automatically as you chat. When you reopen the drawer, your past chats are still available.

### Inline Help ("?" Buttons)

Throughout the training and inference configuration forms, you will see small **?** buttons next to input fields. Clicking a **?** button opens a floating chat panel that:

1. Automatically asks the AI to explain that specific setting and recommend a value.
2. Lets you ask follow-up questions about the setting.
3. Can be dragged around the screen and resized.

This provides context-aware help without leaving the configuration page.

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
