# Error Handling Tool (EHT)

The Error Handling Tool lets you detect and classify errors in image stacks. It is used for quality control of segmentation results — you load a dataset of image layers, review them visually, classify each layer as correct, incorrect, or unsure, and optionally edit masks to fix errors.

## Getting Started: Loading a Dataset

When you first open the Error Handling Tool tab, you see the **Load Dataset** form:

1. **Project Name** — Enter a name for your project (defaults to "My Project").
2. **Dataset Path** — Path to your image data on the server. Supports:
   - Single TIFF file (2D or 3D stack)
   - Directory of images (PNG, JPG, TIFF)
   - Glob pattern (e.g., `/path/to/images/*.tif`)
3. **Mask Path (Optional)** — Path to a corresponding mask file or directory, if available.
4. Click **Load Dataset** to begin.

After loading, the main detection interface appears.

## Main Detection Interface Layout

The interface has three panels:

### Left Panel: Progress Tracker

- **Project Info** — Shows the project name and total number of layers.
- **Progress** — A progress bar showing how many layers have been reviewed out of the total, with a percentage.
- **Classification Summary** — Four counters showing how many layers are classified as:
  - Correct (green checkmark)
  - Incorrect (red X)
  - Unsure (yellow question mark)
  - Unreviewed (gray exclamation mark)
- **Proofread Incorrect Layers** button — Appears when there are layers marked as "incorrect." Clicking it opens the first incorrect layer in the image editor for detailed inspection and mask editing.
- **Load New Dataset** button — Starts a new session by returning to the dataset loader form.

### Center Panel: Layer Grid

Layers are displayed as a paginated grid of thumbnail cards (12 per page, in a 3×4 layout). Each card shows:

- A **thumbnail image** of the layer, with the mask overlaid semi-transparently if a mask exists.
- A **classification ribbon** in the top-right corner showing the current status (Correct, Incorrect, Unsure, or Unreviewed) with a color-coded badge.
- A **checkbox** in the top-left corner for selecting the layer (click the checkbox without opening the editor).
- The **layer name** and **layer number** at the bottom of the card.

**Interactions:**

- **Click a card** to open the Image Inspection modal for detailed viewing and mask editing.
- **Click the checkbox** to select/deselect a layer for bulk classification.
- **Use the pagination controls** at the bottom to navigate between pages.

### Right Panel: Classification Panel

- **Selected count** — A tag showing how many layers are currently selected (e.g., "3 layers selected").
- **Classification buttons:**
  - **Correct (C)** — Green button. Classify selected layers as correct.
  - **Incorrect (X)** — Red button. Classify selected layers as incorrect.
  - **Unsure (U)** — Yellow button. Classify selected layers as unsure.
- **Selection buttons:**
  - **Select All (Ctrl+A)** — Select all layers on the current page.
  - **Clear Selection** — Deselect all layers.
- **Keyboard Shortcuts** reference card at the bottom.

## Keyboard Shortcuts (Main Grid)

These shortcuts work when the main grid is visible (not when the image editor modal is open) and you are not typing in an input field:

| Shortcut | Action                                |
| -------- | ------------------------------------- |
| C        | Classify selected layers as Correct   |
| X        | Classify selected layers as Incorrect |
| U        | Classify selected layers as Unsure    |
| Ctrl+A   | Select all layers on the current page |

## Image Inspection Modal

Click on any layer card to open a full-screen modal for detailed inspection. The modal title shows the layer name and number (e.g., "Image Inspection: layer_042.tif (Layer 43)").

### Modal Header Controls

- **Classification radio buttons** — Toggle between Correct (C), Incorrect (X), and Unsure (U) to set the classification for this individual layer.
- **Save (S)** button — Saves the current mask edits and classification, then closes the modal.

### Modal Layout

The modal contains two areas:

**Left Panel: Tools**

- **Minimap** — A small overview of the full image. Click anywhere on the minimap to jump the main canvas to that location. A red rectangle shows the current viewport.
- **Mode** — Three tool buttons:
  - **Paint (P)** — Draw on the mask to add regions.
  - **Erase (E)** — Remove regions from the mask.
  - **Hand (H)** — Pan the canvas without drawing.
- **Paint/Erase Size** — A slider (1–64) and number input to adjust the brush size. Shown only when Paint or Erase mode is active.
- **History:**
  - **Undo (Ctrl+Z)** — Undo the last brush stroke.
  - **Redo (Ctrl+Shift+Z or Ctrl+Y)** — Redo an undone stroke.
- **Hide/Show Mask** — Toggle the mask overlay visibility.
- **Zoom** — Shows the current zoom percentage. Buttons to zoom in, zoom out, or reset to 100%.

**Center: Canvas**

The main editing area displays the image with the mask overlay. Interactions:

- **Scroll wheel** — Zoom in/out (zooms toward the cursor position).
- **Click and drag** with Paint or Erase tool to draw or erase mask regions. A circular cursor preview follows the mouse showing the brush size.
- **Ctrl+click and drag** or use the **Hand tool** to pan the canvas.

### Image Editor Keyboard Shortcuts

| Shortcut                   | Action                          |
| -------------------------- | ------------------------------- |
| P                          | Switch to Paint mode            |
| E                          | Switch to Erase mode            |
| H                          | Switch to Hand (pan) mode       |
| C                          | Set classification to Correct   |
| X                          | Set classification to Incorrect |
| U                          | Set classification to Unsure    |
| Ctrl+Z / Cmd+Z             | Undo                            |
| Ctrl+Shift+Z / Cmd+Shift+Z | Redo                            |
| Ctrl+Y / Cmd+Y             | Redo (alternative)              |
| Ctrl+S / Cmd+S             | Save mask and classification    |
| Escape                     | Close the modal                 |

## Typical Workflow

1. Load a dataset using the **Load Dataset** form.
2. Review layers in the grid. Use the checkboxes to select batches of obviously correct or incorrect layers.
3. Press **C**, **X**, or **U** to classify selected layers in bulk.
4. Click on questionable layers to open the Image Inspection modal for closer examination.
5. In the modal, use the Paint/Erase tools to correct the mask if needed, set the classification, and press **Save**.
6. Use the **Proofread Incorrect Layers** button to revisit layers you marked as incorrect.
7. Monitor your progress in the Progress Tracker on the left.
