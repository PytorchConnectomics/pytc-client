# Worm Error Handling Page

The Worm Error Handling page provides the same Error Handling Tool interface for detecting and classifying errors, specifically tailored for worm segmentation image stacks.

## How It Works

The Worm Error Handling tab uses the same full Error Handling Tool workflow described in the Error Handling Tool documentation. This includes:

- **Loading a dataset** — Enter a project name, dataset path, and optional mask path, then click **Load Dataset**.
- **Layer grid** — Browse paginated layer thumbnails, select layers with checkboxes, and classify them in bulk.
- **Classification** — Use the **Correct (C)**, **Incorrect (X)**, and **Unsure (U)** buttons or keyboard shortcuts to classify layers.
- **Image Inspection modal** — Click any layer to open a full-screen editor with Paint, Erase, and Hand tools for mask correction, plus undo/redo, zoom, and a minimap.
- **Progress tracking** — Monitor how many layers have been reviewed with the Progress Tracker panel.

## Keyboard Shortcuts

All keyboard shortcuts are identical to the Error Handling Tool:

**Main Grid:**
| Shortcut | Action |
|----------|--------|
| C | Classify selected layers as Correct |
| X | Classify selected layers as Incorrect |
| U | Classify selected layers as Unsure |
| Ctrl+A | Select all layers on the current page |

**Image Editor Modal:**
| Shortcut | Action |
|----------|--------|
| P | Paint mode |
| E | Erase mode |
| H | Hand (pan) mode |
| C | Set classification to Correct |
| X | Set classification to Incorrect |
| U | Set classification to Unsure |
| Ctrl+Z / Cmd+Z | Undo |
| Ctrl+Shift+Z / Cmd+Shift+Z | Redo |
| Ctrl+S / Cmd+S | Save |
| Escape | Close modal |

For the complete workflow guide, see the **Error Handling Tool** documentation.
