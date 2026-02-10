# SynAnno Proofreading Page

The SynAnno (Synapse Annotation) proofreading page lets you review and classify predicted synapse detections. It displays a Neuroglancer 3D viewer alongside a list of synapses and classification controls, enabling efficient annotation workflows.

## Layout

The proofreading page is divided into three panels:

1. **Synapse List (left panel)** — A scrollable list of all synapses in the current project. Each entry shows:
   - **Synapse ID** (e.g., "Synapse #1")
   - **Position** coordinates (x, y, z)
   - **Confidence** score (percentage)
   - **Status icon** — A colored icon indicating the current classification:
     - Green checkmark = Correct
     - Red X = Incorrect
     - Yellow question mark = Unsure
     - No icon = Unreviewed
   - A **progress bar** at the top showing how many synapses have been reviewed out of the total.

2. **Neuroglancer Viewer (center panel)** — A 3D viewer displaying the image volume. When you select a synapse, the viewer centers on that synapse's location. A **Refresh** button appears in the top-right corner to reload the viewer. The current synapse ID is displayed next to the refresh button.

3. **Proofreading Controls (right panel)** — Controls for classifying the selected synapse and editing metadata.

## Reviewing Synapses

1. Click on any synapse in the **Synapse List** to select it. The list highlights the selected synapse with a blue background and left border. The Neuroglancer viewer navigates to that synapse's 3D position.

2. In the **Proofreading Controls** panel, you will see:
   - **Synapse info** — The synapse ID, position, and confidence score.
   - **Status Classification** buttons:
     - **Correct (C)** — Green button. Mark the synapse as a true positive.
     - **Incorrect (X)** — Red button. Mark the synapse as a false positive.
     - **Unsure (U)** — Yellow button. Mark the synapse as uncertain.
   - **Pre-synaptic Neuron ID** — A text input to enter or edit the pre-synaptic neuron ID number.
   - **Post-synaptic Neuron ID** — A text input to enter or edit the post-synaptic neuron ID number.

3. After setting the classification and optionally entering neuron IDs, save your work:
   - Click **Save (S)** to save the current synapse's classification and neuron IDs.
   - Click **Save & Next (→)** to save and automatically advance to the next synapse in the list.

## Keyboard Shortcuts

These shortcuts work when the proofreading page is active and you are not typing in an input field:

| Shortcut        | Action                            |
| --------------- | --------------------------------- |
| C               | Mark current synapse as Correct   |
| X               | Mark current synapse as Incorrect |
| U               | Mark current synapse as Unsure    |
| S               | Save current synapse              |
| Arrow Right (→) | Move to the next synapse          |
| Arrow Left (←)  | Move to the previous synapse      |

## Workflow Tips

- Use **Save & Next** (or press **S** then **→**) for rapid sequential review.
- The progress bar at the top of the synapse list helps you track how many synapses you have reviewed.
- You can click any synapse in the list at any time to jump to it — you do not have to review them in order.
- Neuron ID fields are optional and can be filled in during a second pass.
