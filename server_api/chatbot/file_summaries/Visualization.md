# Visualization Page

The Visualization page lets you view your image and label data in Neuroglancer, a web-based 3D viewer for volumetric data. You can open multiple viewers in separate tabs to compare different datasets side by side.

## How to Visualize Data

1. Navigate to the **Visualization** tab in the top navigation bar.
2. Fill in the following fields:
   - **Image** — Path to your image data file or directory on the server. You can type a path, click the folder icon to browse server files, or drag and drop a file onto the field.
   - **Label** — (Optional) Path to the corresponding label/segmentation data.
   - **Scales (z,y,x)** — The voxel resolution of your data, entered as three comma-separated numbers (e.g., `1,1,1` or `30,8,8`). This tells Neuroglancer how to scale the data for correct 3D rendering.
3. Click the **Visualize** button.

A new Neuroglancer viewer tab will open below the input fields, displaying your data.

## Managing Viewer Tabs

- Each time you click **Visualize** with a new set of inputs, a new viewer tab is created.
- Click on a viewer tab to switch between open viewers.
- Each viewer tab has a **Refresh** button (circular arrow icon) in the top-right corner to reload the viewer if needed.
- Close a viewer tab by clicking the close (×) button on the tab.

## Empty State

When no viewers are open, the page shows a message prompting you to enter image and label paths and click **Visualize** to get started.

## Tips

- Make sure your image and label files are accessible on the server. Use the File Manager to upload or verify file paths.
- The **Scales** field defaults to `1,1,1`. Adjust it to match your dataset's actual voxel resolution for correct spatial rendering.
- Neuroglancer supports common volumetric formats including HDF5, TIFF stacks, and Zarr.
