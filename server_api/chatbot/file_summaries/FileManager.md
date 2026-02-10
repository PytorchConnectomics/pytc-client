# File Manager

The File Manager lets you browse, upload, organize, and manage files and folders on the server. It is the central hub for working with your data before visualization, training, or inference.

## Layout

The File Manager page has three main areas:

1. **Sidebar (left)** — A collapsible folder tree showing your mounted project directories. Click a folder to navigate into it. You can drag the right edge of the sidebar to resize it, or click the collapse button to hide it entirely.

2. **Toolbar (top of main area)** — Contains action buttons and a breadcrumb trail showing your current path. Click any segment in the breadcrumb to jump back to that folder.

3. **File/Folder Grid or List (center)** — Displays the contents of the current folder. You can switch between **Grid View** (icon cards) and **List View** (table with name, size, modified date) using the view toggle buttons in the toolbar.

## Mounting and Unmounting Projects

Before you can browse files, you need to mount a project directory:

1. Click the **Mount Project** button in the toolbar.
2. Enter the server path to the directory you want to mount (e.g., `/data/my_project`).
3. The directory will appear in the sidebar as a top-level folder.

To unmount a project, right-click it in the sidebar and select **Unmount**, or use the **Unmount Project** option in the toolbar.

## Browsing Files

- **Navigate into a folder**: Double-click a folder in the main area, or click it in the sidebar tree.
- **Go back**: Click a parent folder in the breadcrumb trail, or click the **Up** button.
- **Refresh**: Click the **Refresh** button in the toolbar to reload the current folder's contents.

## Creating Files and Folders

- Click the **New Folder** button in the toolbar and enter a name to create a new folder.
- Click the **Upload** button in the toolbar to upload files from your local computer to the current server directory.

## Selecting Items

- **Single select**: Click a file or folder to select it.
- **Multi-select**: Hold **Ctrl** (or **Cmd** on Mac) and click multiple items, or hold **Shift** and click to select a range.
- **Select All**: Press **Ctrl+A** (or **Cmd+A**) to select all items in the current view.

## Context Menu (Right-Click)

Right-click on a file or folder to see available actions:

- **Open** — Open a folder or preview a file
- **Rename** — Change the name of the file or folder
- **Copy** — Copy the item to the clipboard
- **Cut** — Cut the item (move it when pasted)
- **Paste** — Paste copied/cut items into the current folder
- **Delete** — Permanently delete the selected item(s)
- **Properties** — View details such as file size, path, and modification date

You can also right-click on empty space in the main area to access folder-level actions like **New Folder** and **Paste**.

## Drag and Drop

- **Move files/folders**: Drag items from the main area and drop them onto a folder in the sidebar or main area to move them.
- **Upload from desktop**: Drag files from your desktop or file explorer and drop them into the main area to upload them to the current server directory.

## File Preview

Click on a file (single click or via the context menu **Open** action) to preview it. Supported preview types include images (PNG, JPG, TIFF) and text files.

## Toolbar Actions Summary

| Button | Action |
|--------|--------|
| Mount Project | Add a server directory to the sidebar |
| Unmount Project | Remove a mounted directory from the sidebar |
| New Folder | Create a new folder in the current directory |
| Upload | Upload files from your local machine |
| Refresh | Reload the current folder contents |
| Grid View / List View | Toggle between icon grid and detail table |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+A / Cmd+A | Select all items |
| Delete / Backspace | Delete selected items |
| Ctrl+C / Cmd+C | Copy selected items |
| Ctrl+X / Cmd+X | Cut selected items |
| Ctrl+V / Cmd+V | Paste items |
| Enter | Open/navigate into selected item |

## File Input Fields (Used Across the App)

Throughout the application (e.g., when selecting image paths for training or visualization), file path inputs support three ways to choose a file or folder:

1. **Type a path** — Manually type or paste a server path into the text field.
2. **Browse** — Click the folder icon on the left side of the input to open a file picker dialog. The picker shows your mounted server directories and lets you navigate and select files or folders.
3. **Drag and drop** — Drag a file from your desktop onto the input field to set its path.
