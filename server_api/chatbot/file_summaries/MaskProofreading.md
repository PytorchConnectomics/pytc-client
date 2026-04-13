# Mask Proofreading Page

The Mask Proofreading page lets you review and correct segmentation masks on a per-instance basis. You load a volume (image stack) along with its mask, and the tool automatically detects individual instances (connected components). You can then step through each instance, view it from multiple axes, classify it, and paint or erase mask regions directly on the canvas.

## Getting Started: Loading a Dataset

When you first open the Mask Proofreading tab, you see the **Start a Mask Proofreading Session** form:

1. **Project Name** — Enter a name for your proofreading session (defaults to "My Project").
2. **Dataset Path** — Path to your image volume on the server. Supports a single TIFF file, a directory of images, or a glob pattern (e.g., `/path/to/images/*.tif`).
3. **Mask Path (Optional)** — Path to a corresponding mask file or directory. Providing a mask enables instance proofreading.
4. Click **Load Dataset** to begin.

After loading, the tool builds an instance list from the mask and displays the main proofreading interface.

## Main Interface Layout

The interface has two main areas:

### Center: Canvas and Slice Slider

The canvas displays the current slice of the volume with mask overlays. Below the canvas is a **slice slider** that lets you scrub through slices along the active axis.

- The current axis and slice number are shown in the inspector sidebar header (e.g., "XY Slice 42").
- Drag the slider to scrub through slices quickly. The tool prefetches nearby slices for smooth scrubbing.
- The canvas supports the same **Paint**, **Erase**, and **Hand** tools as the old image editor (see Editing Tools below).

Above the canvas are two buttons:

- **Focus canvas** — Hides the inspector sidebar to give the canvas more room.
- **Show sidebar** — Brings the sidebar back.

### Right Sidebar: Inspector

The inspector sidebar is organized into collapsible sections:

**Review** — Classification controls for the selected instance:

- **Looks good** (green) — Mark the instance as correctly segmented.
- **Needs fix** (red) — Mark the instance as needing correction.
- **Unsure** (yellow) — Mark the instance as uncertain.

**Instances** — Controls for navigating instances:

- **Browse...** — Opens a drawer with the full instance list (see Instance Navigator below).
- **Next unreviewed** — Jumps to the next instance that has not been classified yet.
- **More menu (⋯)** — Contains **Export edited masks** and **Overwrite source masks** options.

**Overlay** — Opacity sliders for mask overlays:

- **Other instances** — Controls how visible non-selected instances are (default 8%).
- **Selected instance** — Controls how visible the active instance is (default 80%).

**Progress** — Shows review progress:

- A progress bar showing how many instances have been reviewed out of the total.
- Counters for correct, incorrect, unsure, and unreviewed instances.
- **Load dataset** button to start a new session.

## Instance Navigator

Click **Browse...** in the Instances section (or the Instance Navigator drawer) to see all detected instances. Each entry shows:

- **Instance ID** (e.g., "#42")
- **Center of mass** coordinates (z, y, x)
- **Voxel count** — the size of the instance
- **Classification status** — color-coded tag: "reviewed" (green), "needs fix" (red), "unsure" (gold), or "unreviewed" (gray)

You can:

- **Filter** instances by ID using the search box at the top.
- **Navigate** with the left/right arrow buttons to move between instances.
- **Click** any instance to select it. The canvas jumps to that instance's center-of-mass slice.

## Multi-Axis Viewing

You can view the volume from three axes:

- **XY** — The default top-down view
- **ZX** — A side view
- **ZY** — Another side view

Switch axes using the axis selector in the canvas toolbar. The slice slider updates to reflect the depth along the chosen axis. When you select a new instance, the slice automatically jumps to the instance's center of mass along the current axis.

## Editing Tools (Canvas)

The canvas includes a collapsible tool panel for mask editing:

- **Paint (P)** — Draw on the mask to add regions. Adjust brush size with a slider (1–64).
- **Erase (E)** — Remove regions from the mask. Adjust brush size with a slider (1–64).
- **Hand (H)** — Pan the canvas without drawing.
- **Undo (Ctrl+Z / Cmd+Z)** — Undo the last brush stroke.
- **Redo (Ctrl+Shift+Z / Cmd+Shift+Z)** — Redo an undone stroke.
- **Hide/Show Mask** — Toggle mask overlay visibility.
- **Zoom** — Scroll wheel to zoom in/out. Zoom percentage is displayed.
- **Save (Ctrl+S / Cmd+S)** — Save mask edits for the current instance and slice.

## Exporting Edited Masks

After editing masks, you can save your work:

- **Export edited masks** — Opens a dialog where you enter an output path. The tool writes a TIFF file containing all your edits.
- **Overwrite source masks** — Writes edits back to the original mask file. A timestamped backup is always created first.

## Keyboard Shortcuts

**Instance navigation and classification** (active when an instance is selected):

| Shortcut    | Action                         |
| ----------- | ------------------------------ |
| C           | Classify instance as correct   |
| X           | Classify instance as needs fix |
| U           | Classify instance as unsure    |
| Arrow Right | Go to next instance            |
| Arrow Left  | Go to previous instance        |
| 1           | Switch to XY axis              |
| 2           | Switch to ZX axis              |
| 3           | Switch to ZY axis              |

**Canvas editing tools** (active when the editor canvas is focused):

| Shortcut                   | Action                    |
| -------------------------- | ------------------------- |
| P                          | Switch to Paint mode      |
| E                          | Switch to Erase mode      |
| H                          | Switch to Hand (pan) mode |
| A / Arrow Left             | Previous slice            |
| D / Arrow Right            | Next slice                |
| Ctrl+Z / Cmd+Z             | Undo                      |
| Ctrl+Shift+Z / Cmd+Shift+Z | Redo                      |
| Ctrl+Y / Cmd+Y             | Redo (alternative)        |
| Ctrl+S / Cmd+S             | Save mask edits           |

## Typical Workflow

1. Open the **Mask Proofreading** tab and load a dataset with a mask.
2. The tool detects instances and displays the first one.
3. Use the **Instance Navigator** (Browse...) to see all instances, or click **Next unreviewed** to step through them.
4. For each instance, examine it from different axes if needed, then classify it as **Looks good**, **Needs fix**, or **Unsure**.
5. If the mask needs correction, use the **Paint** and **Erase** tools on the canvas, then click **Save**.
6. Track your progress in the **Progress** section of the inspector sidebar.
7. When finished, use **Export edited masks** or **Overwrite source masks** to save all changes.
