import React, { useState, useEffect, useRef, useContext } from "react";
import {
  Button,
  Dropdown,
  Input,
  Modal,
  message,
  Menu,
  Breadcrumb,
  Empty,
  Image,
  Spin,
} from "antd";
import {
  FolderFilled,
  FolderOpenOutlined,
  FileOutlined,
  FileTextOutlined,
  ArrowLeftOutlined,
  AppstoreOutlined,
  BarsOutlined,
  UploadOutlined,
  EyeOutlined,
  LayoutOutlined,
  MoreOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { apiClient } from "../api";
import FileTreeSidebar from "../components/FileTreeSidebar";
import { openLocalFile, revealInFinder } from "../electronApi";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";

const HIDDEN_SYSTEM_FILES = new Set([
  "workflow_preference.json",
  ".pytc_proofreading.json",
  ".pytc_instance_labels.tif",
  ".ds_store",
  "thumbs.db",
]);
const IMAGE_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".bmp",
  ".tif",
  ".tiff",
  ".webp",
  ".h5",
  ".hdf5",
  ".npy",
  ".npz",
  ".zarr",
  ".n5",
  ".nii",
  ".nii.gz",
  ".mrc",
  ".mrcs",
]);
const PROJECT_ROLE_LABELS = {
  image: "image",
  label: "label",
  prediction: "prediction",
  config: "config",
  checkpoint: "checkpoint",
  volume: "other volume",
};

const joinProjectPath = (rootPath, relativePath) => {
  if (!rootPath || !relativePath) return "";
  return `${String(rootPath).replace(/\/+$/, "")}/${String(relativePath).replace(/^\/+/, "")}`;
};

const buildWorkflowPatchFromProjectSuggestion = (suggestion) => {
  const profile = suggestion?.profile || {};
  const examples = profile.examples || {};
  const paired = profile.paired_examples?.[0] || {};
  const rootPath = suggestion?.directory_path;
  const imageRelative = paired.image || examples.image?.[0];
  const labelRelative = paired.label || examples.label?.[0];
  const predictionRelative = examples.prediction?.[0];
  const checkpointRelative = examples.checkpoint?.[0];
  const patch = {
    dataset_path: rootPath || null,
    image_path: joinProjectPath(rootPath, imageRelative) || null,
    label_path: joinProjectPath(rootPath, labelRelative) || null,
    mask_path: joinProjectPath(rootPath, labelRelative) || null,
    inference_output_path: joinProjectPath(rootPath, predictionRelative) || null,
    checkpoint_path: joinProjectPath(rootPath, checkpointRelative) || null,
  };
  return Object.fromEntries(
    Object.entries(patch).filter(([, value]) => Boolean(value)),
  );
};

const collectDescendantFolderIds = (folderList, rootIds) => {
  const removed = new Set();
  const queue = [...rootIds];

  while (queue.length > 0) {
    const currentId = queue.shift();
    if (removed.has(currentId)) {
      continue;
    }
    removed.add(currentId);
    folderList
      .filter((folder) => folder.parent === currentId)
      .forEach((folder) => queue.push(folder.key));
  }

  return removed;
};

const isFolderWithinSubtree = (folderList, rootId, targetId) => {
  if (!rootId || !targetId || rootId === "root" || targetId === "root") {
    return false;
  }

  let current = folderList.find((folder) => folder.key === targetId);
  while (current) {
    if (current.key === rootId) {
      return true;
    }
    if (!current.parent || current.parent === "root") {
      break;
    }
    current = folderList.find((folder) => folder.key === current.parent);
  }
  return false;
};

// Transform backend file list into UI state
const transformFiles = (fileList) => {
  const folders = [];
  const files = {};
  fileList.forEach((f) => {
    const nameLower = String(f.name || "").toLowerCase();
    if (!f.is_folder && HIDDEN_SYSTEM_FILES.has(nameLower)) {
      return;
    }
    if (f.is_folder) {
      folders.push({
        key: String(f.id),
        title: f.name,
        parent: f.path ? String(f.path) : "root",
        is_folder: true,
        physical_path: f.physical_path || null,
      });
    } else {
      const parentKey = f.path || "root";
      if (!files[parentKey]) files[parentKey] = [];
      files[parentKey].push({
        key: String(f.id),
        name: f.name,
        size: f.size,
        type: f.type,
        is_folder: false,
        physical_path: f.physical_path || null,
      });
    }
  });
  return { folders, files };
};

function FilesManager() {
  const context = useContext(AppContext);
  const workflowContext = useWorkflow();
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState({});
  const foldersRef = useRef([]);
  const filesRef = useRef({});
  const [currentFolder, setCurrentFolder] = useState("root");
  const [loadedParents, setLoadedParents] = useState([]);
  const [loadingParents, setLoadingParents] = useState([]);
  const loadedParentsRef = useRef(new Set());
  const loadingParentsRef = useRef(new Set());
  const [expandedFolders, setExpandedFolders] = useState([]);
  const [viewMode, setViewMode] = useState("grid"); // 'grid' or 'list'
  const [selectedItems, setSelectedItems] = useState([]);
  const [clipboard, setClipboard] = useState({ items: [], action: null }); // copy / move
  const [editingItem, setEditingItem] = useState(null);
  const [newItemType, setNewItemType] = useState(null);
  const [tempName, setTempName] = useState("");
  const inputRef = useRef(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [previewFile, setPreviewFile] = useState(null);
  const [propertiesData, setPropertiesData] = useState(null);
  const [selectionBox, setSelectionBox] = useState(null);
  const [serverUnavailable, setServerUnavailable] = useState(false);
  const [hasShownServerWarning, setHasShownServerWarning] = useState(false);
  const [previewStatus, setPreviewStatus] = useState({});
  const [projectSuggestions, setProjectSuggestions] = useState([]);
  const containerRef = useRef(null);
  const itemRefs = useRef({});
  const isDragSelecting = useRef(false);
  const previewBaseUrl = apiClient.defaults.baseURL || "http://localhost:4242";

  // Sidebar Resize Logic
  const [sidebarWidth, setSidebarWidth] = useState(250);
  const [isResizing, setIsResizing] = useState(false);
  const [isSidebarVisible, setIsSidebarVisible] = useState(true);

  const startResizing = React.useCallback(() => setIsResizing(true), []);
  const stopResizing = React.useCallback(() => setIsResizing(false), []);
  const resize = React.useCallback(
    (mouseMoveEvent) => {
      if (isResizing) {
        // Simple resize logic assuming sidebar is on the left
        const newWidth = mouseMoveEvent.clientX;
        if (newWidth > 100 && newWidth < 600) {
          setSidebarWidth(newWidth);
        }
      }
    },
    [isResizing],
  );

  useEffect(() => {
    window.addEventListener("mousemove", resize);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [resize, stopResizing]);

  // Focus input when editing starts
  useEffect(() => {
    if (editingItem && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingItem]);

  useEffect(() => {
    foldersRef.current = folders;
  }, [folders]);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  const syncLoadedParents = React.useCallback((nextParents) => {
    loadedParentsRef.current = new Set(nextParents);
    setLoadedParents(nextParents);
  }, []);

  const syncLoadingParents = React.useCallback((nextParents) => {
    loadingParentsRef.current = new Set(nextParents);
    setLoadingParents(nextParents);
  }, []);

  const markParentLoaded = React.useCallback(
    (parentKey) => {
      if (loadedParentsRef.current.has(parentKey)) {
        return;
      }
      syncLoadedParents([...loadedParentsRef.current, parentKey]);
    },
    [syncLoadedParents],
  );

  const setParentLoadingState = React.useCallback(
    (parentKey, isLoading) => {
      const nextParents = new Set(loadingParentsRef.current);
      if (isLoading) {
        nextParents.add(parentKey);
      } else {
        nextParents.delete(parentKey);
      }
      syncLoadingParents(Array.from(nextParents));
    },
    [syncLoadingParents],
  );

  const resetLocalFileCache = React.useCallback(() => {
    foldersRef.current = [];
    filesRef.current = {};
    setFolders([]);
    setFiles({});
    syncLoadedParents([]);
    syncLoadingParents([]);
    setExpandedFolders([]);
  }, [syncLoadedParents, syncLoadingParents]);

  const replaceFolderChildren = React.useCallback(
    (parentKey, fileList) => {
      const normalizedParent = String(parentKey || "root");
      const previousFolders = foldersRef.current;
      const previousFiles = filesRef.current;
      const { folders: nextFolders, files: nextFiles } = transformFiles(fileList);
      const existingDirectChildIds = previousFolders
        .filter((folder) => folder.parent === normalizedParent)
        .map((folder) => folder.key);
      const nextDirectChildIds = new Set(nextFolders.map((folder) => folder.key));
      const removedFolderIds = collectDescendantFolderIds(
        previousFolders,
        existingDirectChildIds.filter((id) => !nextDirectChildIds.has(id)),
      );

      const mergedFolders = [
        ...previousFolders.filter(
          (folder) =>
            folder.parent !== normalizedParent && !removedFolderIds.has(folder.key),
        ),
        ...nextFolders,
      ].sort((left, right) => {
        if (left.parent === right.parent) {
          return String(left.title || "").localeCompare(String(right.title || ""));
        }
        return String(left.parent || "").localeCompare(String(right.parent || ""));
      });

      const mergedFiles = { ...previousFiles };
      delete mergedFiles[normalizedParent];
      removedFolderIds.forEach((folderId) => {
        delete mergedFiles[folderId];
      });
      Object.entries(nextFiles).forEach(([key, value]) => {
        mergedFiles[key] = value;
      });

      foldersRef.current = mergedFolders;
      filesRef.current = mergedFiles;
      setFolders(mergedFolders);
      setFiles(mergedFiles);
      markParentLoaded(normalizedParent);
    },
    [markParentLoaded],
  );

  const removeFolderSubtrees = React.useCallback(
    (folderIds) => {
      if (!folderIds.length) {
        return;
      }

      const removedFolderIds = collectDescendantFolderIds(
        foldersRef.current,
        folderIds,
      );
      const nextFolders = foldersRef.current.filter(
        (folder) => !removedFolderIds.has(folder.key),
      );
      const nextFiles = { ...filesRef.current };
      removedFolderIds.forEach((folderId) => {
        delete nextFiles[folderId];
      });

      foldersRef.current = nextFolders;
      filesRef.current = nextFiles;
      setFolders(nextFolders);
      setFiles(nextFiles);
      syncLoadedParents(
        Array.from(loadedParentsRef.current).filter(
          (parentKey) => !removedFolderIds.has(parentKey),
        ),
      );
      setExpandedFolders((prev) =>
        prev.filter((key) => !removedFolderIds.has(key.replace("folder-", ""))),
      );
    },
    [syncLoadedParents],
  );

  const fetchFolderContents = React.useCallback(
    async (parentKey, options = {}) => {
      const normalizedParent = String(parentKey || "root");
      const { force = false, silentNetworkError = false } = options;

      if (
        !force &&
        loadedParentsRef.current.has(normalizedParent) &&
        !loadingParentsRef.current.has(normalizedParent)
      ) {
        return {
          folders: foldersRef.current.filter(
            (folder) => folder.parent === normalizedParent,
          ),
          files: filesRef.current[normalizedParent] || [],
        };
      }

      if (loadingParentsRef.current.has(normalizedParent)) {
        return null;
      }

      setParentLoadingState(normalizedParent, true);
      try {
        const res = await apiClient.get("/files", {
          params: { parent: normalizedParent },
        });
        replaceFolderChildren(normalizedParent, res.data);
        setServerUnavailable(false);
        return res.data;
      } catch (err) {
        const isNetworkError = !err.response;
        if (isNetworkError) {
          setServerUnavailable(true);
          if (!hasShownServerWarning && !silentNetworkError) {
            setHasShownServerWarning(true);
          }
        }
        if (!err.isAuthError && !isNetworkError) {
          console.error("Failed to load files", err);
          message.error("Could not load files");
        }
        return null;
      } finally {
        setParentLoadingState(normalizedParent, false);
      }
    },
    [
      hasShownServerWarning,
      replaceFolderChildren,
      setParentLoadingState,
    ],
  );

  // Load initial data with proper cleanup and 401 handling
  useEffect(() => {
    let isMounted = true; // Prevent state updates after unmount

    const loadVisibleFolders = async () => {
      if (!isMounted) return;
      await fetchFolderContents("root");
      if (currentFolder !== "root") {
        await fetchFolderContents(currentFolder);
      }
    };

    loadVisibleFolders();
    const retryId = setInterval(() => {
      if (isMounted && serverUnavailable) {
        fetchFolderContents("root", {
          force: true,
          silentNetworkError: true,
        });
        if (currentFolder !== "root") {
          fetchFolderContents(currentFolder, {
            force: true,
            silentNetworkError: true,
          });
        }
      }
    }, 2000);

    // Cleanup function to prevent state updates after unmount
    return () => {
      isMounted = false;
      clearInterval(retryId);
    };
  }, [currentFolder, fetchFolderContents, serverUnavailable]); // Retry when server unavailable

  const getCurrentFolderObj = () =>
    folders.find((f) => f.key === currentFolder);
  // eslint-disable-next-line no-loop-func
  const getBreadcrumbs = () => {
    const path = [{ key: "root", title: "Projects", parent: null }];
    if (currentFolder === "root") {
      return path;
    }
    const chain = [];
    let curr = getCurrentFolderObj();
    while (curr) {
      chain.unshift(curr);
      if (!curr.parent || curr.parent === "root") break;
      curr = folders.find((f) => f.key === curr.parent);
    }
    return path.concat(chain);
  };

  const handleNavigate = (key) => {
    if (key !== "root") {
      fetchFolderContents(key);
      setExpandedFolders((prev) =>
        prev.includes(`folder-${key}`) ? prev : [...prev, `folder-${key}`],
      );
    }
    setCurrentFolder(key);
    setSelectedItems([]);
    setEditingItem(null);
    setNewItemType(null);
  };

  const loadProjectSuggestions = React.useCallback(async () => {
    try {
      const response = await apiClient.get("/files/project-suggestions", {
        withCredentials: true,
      });
      setProjectSuggestions(response.data || []);
    } catch (error) {
      // Suggestions are convenience only; normal mounting must keep working.
      console.warn("Could not load project suggestions", error);
      setProjectSuggestions([]);
    }
  }, []);

  useEffect(() => {
    loadProjectSuggestions();
  }, [loadProjectSuggestions]);

  const isImageFile = (file) => {
    if (!file || file.is_folder) return false;
    if (file.type && file.type.startsWith("image/")) return true;
    const name = String(file.name || "").toLowerCase();
    const ext = `.${name.split(".").pop()}`;
    return IMAGE_EXTENSIONS.has(ext) || name.endsWith(".nii.gz");
  };

  const getPreviewUrl = (fileKey) =>
    `${previewBaseUrl}/files/preview/${fileKey}`;

  const markPreviewLoaded = (id) => {
    setPreviewStatus((prev) => ({ ...prev, [id]: "loaded" }));
  };

  const markPreviewError = (id) => {
    setPreviewStatus((prev) => ({ ...prev, [id]: "error" }));
  };

  const handleUp = () => {
    const curr = getCurrentFolderObj();
    if (curr && curr.parent) handleNavigate(curr.parent);
  };

  // Folder creation
  const startCreateFolder = () => {
    const key = `new_folder_${Date.now()}`;
    setNewItemType("folder");
    setEditingItem(key);
    setTempName("");
  };

  const finishCreateFolder = async () => {
    if (!tempName.trim()) {
      setEditingItem(null);
      setNewItemType(null);
      return;
    }
    // Check for duplicate name
    const existing =
      folders.some((f) => f.parent === currentFolder && f.title === tempName) ||
      (files[currentFolder] || []).some((f) => f.name === tempName);
    if (existing) {
      message.error("A file or folder with this name already exists.");
      return;
    }
    try {
      const payload = { name: tempName, path: currentFolder };
      const res = await apiClient.post(`/files/folder`, payload, {
        withCredentials: true,
      });
      const newFolder = res.data;
      setFolders([
        ...folders,
        {
          key: String(newFolder.id),
          title: newFolder.name,
          parent: newFolder.path,
        },
      ]);
      setFiles({ ...files, [String(newFolder.id)]: [] });
      message.success("Folder created");
    } catch (err) {
      console.error(err);
      message.error("Failed to create folder");
    }
    setEditingItem(null);
    setNewItemType(null);
  };

  // Rename
  const startRename = (key, currentName) => {
    setEditingItem(key);
    setTempName(currentName);
  };

  const finishRename = async () => {
    if (!tempName.trim()) {
      setEditingItem(null);
      return;
    }
    const key = editingItem;
    const isFolder = folders.some((f) => f.key === key);
    const targetPath = isFolder
      ? folders.find((f) => f.key === key).parent
      : currentFolder;

    // Check for duplicate name
    const existing =
      folders.some(
        (f) => f.parent === targetPath && f.title === tempName && f.key !== key,
      ) ||
      (files[targetPath] || []).some(
        (f) => f.name === tempName && f.key !== key,
      );

    if (existing) {
      message.error("A file or folder with this name already exists.");
      // Restore original name
      const originalItem = isFolder
        ? folders.find((f) => f.key === key)
        : (files[targetPath] || []).find((f) => f.key === key);
      if (originalItem) {
        setTempName(originalItem.title || originalItem.name);
      }
      return;
    }
    try {
      await apiClient.put(
        `/files/${key}`,
        { name: tempName, path: isFolder ? undefined : currentFolder },
        { withCredentials: true },
      );
      if (isFolder) {
        setFolders(
          folders.map((f) => (f.key === key ? { ...f, title: tempName } : f)),
        );
      } else {
        setFiles((prev) => ({
          ...prev,
          [currentFolder]: prev[currentFolder].map((f) =>
            f.key === key ? { ...f, name: tempName } : f,
          ),
        }));
      }
      message.success("Renamed successfully");
    } catch (err) {
      console.error(err);
      message.error("Rename failed");
    }
    setEditingItem(null);
  };

  // Delete
  const handleDelete = async (keys = selectedItems) => {
    if (keys.length === 0) return;
    try {
      await Promise.all(
        keys.map((id) =>
          apiClient.delete(`/files/${id}`, { withCredentials: true }),
        ),
      );
      const folderIds = keys.filter((k) => folders.some((f) => f.key === k));
      const fileIds = keys.filter((k) => !folderIds.includes(k));
      const removedFolderIds = collectDescendantFolderIds(
        foldersRef.current,
        folderIds,
      );
      const nextFolders = foldersRef.current.filter(
        (folder) => !removedFolderIds.has(folder.key),
      );
      const nextFiles = { ...filesRef.current };
      Object.keys(nextFiles).forEach((folderKey) => {
        nextFiles[folderKey] = nextFiles[folderKey].filter(
          (file) => !fileIds.includes(file.key),
        );
      });
      removedFolderIds.forEach((folderId) => {
        delete nextFiles[folderId];
      });
      foldersRef.current = nextFolders;
      filesRef.current = nextFiles;
      setFolders(nextFolders);
      setFiles(nextFiles);
      syncLoadedParents(
        Array.from(loadedParentsRef.current).filter(
          (parentKey) => !removedFolderIds.has(parentKey),
        ),
      );
      setExpandedFolders((prev) =>
        prev.filter((key) => !removedFolderIds.has(key.replace("folder-", ""))),
      );
      setSelectedItems([]);
      message.success(`Deleted ${keys.length} items`);
    } catch (err) {
      console.error(err);
      message.error("Delete failed");
    }
  };

  // Copy / Paste (simple copy creates a new entry via folder endpoint for demo)
  const handleCopy = (keys = selectedItems) => {
    if (keys.length === 0) return;
    setClipboard({ items: keys, action: "copy" });
    message.info("Copied to clipboard");
  };

  const handleCut = (keys = selectedItems) => {
    if (keys.length === 0) return;
    setClipboard({ items: keys, action: "move" });
    message.info("Cut to clipboard");
  };

  const handlePaste = async () => {
    if (!clipboard.items.length) return;

    if (clipboard.action === "copy") {
      const newEntries = [];
      for (const id of clipboard.items) {
        // Find original item to get name (for UI update if needed, though backend handles naming)
        const orig = Object.values(files)
          .flat()
          .find((f) => f.key === id);
        if (!orig) continue;

        try {
          const res = await apiClient.post(
            `/files/copy`,
            {
              source_id: parseInt(id),
              destination_path: currentFolder,
            },
            { withCredentials: true },
          );

          const newFile = res.data;
          newEntries.push({
            key: String(newFile.id),
            name: newFile.name,
            size: newFile.size,
            type: newFile.type,
          });
        } catch (err) {
          console.error("Paste error", err);
          message.error(`Failed to copy item ${id}`);
        }
      }
      if (newEntries.length) {
        setFiles((prev) => ({
          ...prev,
          [currentFolder]: [...(prev[currentFolder] || []), ...newEntries],
        }));
        message.success("Pasted items");
      }
    } else if (clipboard.action === "move") {
      let moved = 0;
      for (const id of clipboard.items) {
        // Find item (could be folder or file)
        const isFolder = folders.some((f) => f.key === id);
        const item = isFolder
          ? folders.find((f) => f.key === id)
          : Object.values(files)
              .flat()
              .find((f) => f.key === id);

        if (!item) continue;
        // Skip if already in current folder
        if (
          (isFolder && item.parent === currentFolder) ||
          (!isFolder && files[currentFolder]?.some((f) => f.key === id))
        )
          continue;

        try {
          await apiClient.put(
            `/files/${id}`,
            {
              name: item.title || item.name,
              path: currentFolder,
            },
            { withCredentials: true },
          );

          if (isFolder) {
            setFolders((prev) =>
              prev.map((f) =>
                f.key === id ? { ...f, parent: currentFolder } : f,
              ),
            );
          } else {
            setFiles((prev) => {
              const sourceFolder = Object.keys(prev).find((fk) =>
                prev[fk].some((f) => f.key === id),
              );
              if (!sourceFolder) return prev;
              const fileObj = prev[sourceFolder].find((f) => f.key === id);
              const newSource = prev[sourceFolder].filter((f) => f.key !== id);
              const newTarget = [...(prev[currentFolder] || []), fileObj];
              return {
                ...prev,
                [sourceFolder]: newSource,
                [currentFolder]: newTarget,
              };
            });
          }
          moved++;
        } catch (err) {
          console.error("Paste move error", err);
        }
      }
      if (moved) {
        message.success(`Moved ${moved} items`);
        setClipboard({ items: [], action: null }); // Clear clipboard after move
      }
    }
  };

  // Preview
  const handlePreview = (key) => {
    const file = (files[currentFolder] || []).find((f) => f.key === key);
    if (file) setPreviewFile(file);
  };

  // Properties
  const handleProperties = (keys = selectedItems) => {
    if (keys.length === 0) return;

    if (keys.length === 1) {
      // Single item - show detailed info
      const key = keys[0];
      const folder = folders.find((f) => f.key === key);
      const file = Object.values(files)
        .flat()
        .find((f) => f.key === key);
      const item = folder || file;

      if (item) {
        const isMountedFolder =
          !!folder && folder.parent === "root" && folder.physical_path;
        let descendantFileCount = 0;
        let descendantFolderCount = 0;
        let descendantSizeKb = 0;

        if (isMountedFolder) {
          const queue = [folder.key];
          while (queue.length) {
            const parentId = queue.shift();
            const childFolders = folders.filter((f) => f.parent === parentId);
            descendantFolderCount += childFolders.length;
            childFolders.forEach((f) => queue.push(f.key));

            const childFiles = files[parentId] || [];
            descendantFileCount += childFiles.length;
            childFiles.forEach((f) => {
              const sizeStr = String(f.size || "");
              const match = sizeStr.match(/([0-9.]+)\s*(KB|MB|GB|B)/i);
              if (match) {
                const value = parseFloat(match[1]);
                const unit = match[2].toUpperCase();
                if (unit === "B") descendantSizeKb += value / 1024;
                if (unit === "KB") descendantSizeKb += value;
                if (unit === "MB") descendantSizeKb += value * 1024;
                if (unit === "GB") descendantSizeKb += value * 1024 * 1024;
              }
            });
          }
        }

        const totalSizeStr = isMountedFolder
          ? descendantSizeKb > 1024
            ? `${(descendantSizeKb / 1024).toFixed(2)} MB`
            : `${descendantSizeKb.toFixed(2)} KB`
          : item.size || "N/A";

        setPropertiesData({
          type: "single",
          name: item.title || item.name,
          isFolder: !!folder,
          size: totalSizeStr,
          fileType: item.type || "Folder",
          created: new Date().toLocaleString(), // Backend should provide this
          modified: new Date().toLocaleString(), // Backend should provide this
          fileCount: isMountedFolder ? descendantFileCount : undefined,
          folderCount: isMountedFolder ? descendantFolderCount : undefined,
          isMountedFolder,
        });
      }
    } else {
      // Multiple items - show summary
      const folderKeys = keys.filter((k) => folders.some((f) => f.key === k));
      const fileKeys = keys.filter((k) => !folderKeys.includes(k));

      // Calculate total size (simplified - would need backend support for accurate calculation)
      let totalSize = 0;
      fileKeys.forEach((key) => {
        const file = Object.values(files)
          .flat()
          .find((f) => f.key === key);
        if (file && file.size) {
          // Parse size string (e.g., "1.5MB" or "500KB")
          const sizeStr = String(file.size);
          const match = sizeStr.match(/([0-9.]+)\s*(KB|MB|GB)/i);
          if (match) {
            const value = parseFloat(match[1]);
            const unit = match[2].toUpperCase();
            if (unit === "KB") totalSize += value;
            else if (unit === "MB") totalSize += value * 1024;
            else if (unit === "GB") totalSize += value * 1024 * 1024;
          }
        }
      });

      const totalSizeStr =
        totalSize > 1024
          ? `${(totalSize / 1024).toFixed(2)} MB`
          : `${totalSize.toFixed(2)} KB`;

      setPropertiesData({
        type: "multiple",
        totalCount: keys.length,
        folderCount: folderKeys.length,
        fileCount: fileKeys.length,
        totalSize: totalSizeStr,
      });
    }
  };

  // Drag & Drop
  const handleDragStart = (e, key, type) => {
    let itemsToDrag = selectedItems;
    if (!selectedItems.includes(key)) {
      itemsToDrag = [key];
      setSelectedItems([key]);
    }
    e.dataTransfer.setData("text/plain", JSON.stringify({ keys: itemsToDrag }));
  };

  const handleDragOver = (e) => e.preventDefault();

  const handleDrop = async (e, targetFolderKey) => {
    e.preventDefault();

    // Check if dropping files from OS (external files)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleExternalFileDrop(e.dataTransfer.files, targetFolderKey);
      return;
    }

    // Handle internal drag-and-drop
    const dataStr = e.dataTransfer.getData("text/plain");
    if (!dataStr) return;
    const { keys } = JSON.parse(dataStr);
    if (!keys || keys.length === 0) return;
    if (keys.includes(targetFolderKey)) return;

    let moved = 0;
    for (const key of keys) {
      const isFolder = folders.some((f) => f.key === key);
      const item = isFolder
        ? folders.find((f) => f.key === key)
        : Object.values(files)
            .flat()
            .find((f) => f.key === key);

      if (!item) continue;

      try {
        // Send name along with path to fix 422 error
        await apiClient.put(
          `/files/${key}`,
          {
            name: item.title || item.name,
            path: targetFolderKey,
          },
          { withCredentials: true },
        );

        if (isFolder) {
          setFolders((prev) =>
            prev.map((f) =>
              f.key === key ? { ...f, parent: targetFolderKey } : f,
            ),
          );
        } else {
          setFiles((prev) => {
            const sourceFolder = Object.keys(prev).find((fk) =>
              prev[fk].some((f) => f.key === key),
            );
            if (!sourceFolder) return prev;
            const fileObj = prev[sourceFolder].find((f) => f.key === key);
            const newSource = prev[sourceFolder].filter((f) => f.key !== key);
            const newTarget = [...(prev[targetFolderKey] || []), fileObj];
            return {
              ...prev,
              [sourceFolder]: newSource,
              [targetFolderKey]: newTarget,
            };
          });
        }
        moved++;
      } catch (err) {
        console.error("Move error", err);
        message.error(`Failed to move ${item.title || item.name}`);
      }
    }
    if (moved) {
      message.success(`Moved ${moved} items`);
      setSelectedItems([]);
    }
  };

  // Handle external file drops from OS
  const handleExternalFileDrop = async (fileList, targetFolder) => {
    const filesArray = Array.from(fileList);
    let uploaded = 0;

    for (const file of filesArray) {
      const form = new FormData();
      form.append("file", file);
      form.append("path", targetFolder);

      try {
        const res = await apiClient.post(`/files/upload`, form, {
          headers: { "Content-Type": "multipart/form-data" },
          withCredentials: true,
        });
        const newFile = res.data;
        setFiles((prev) => ({
          ...prev,
          [targetFolder]: [
            ...(prev[targetFolder] || []),
            {
              key: String(newFile.id),
              name: newFile.name,
              size: newFile.size,
              type: newFile.type,
            },
          ],
        }));
        uploaded++;
      } catch (err) {
        console.error("Upload error", err);
        message.error(`Failed to upload ${file.name}`);
      }
    }

    if (uploaded > 0) {
      message.success(`Uploaded ${uploaded} file${uploaded > 1 ? "s" : ""}`);
    }
  };

  // Selection box handling
  const handleMouseDown = (e) => {
    if (
      e.target !== containerRef.current &&
      e.target.className !== "file-manager-content"
    )
      return;
    isDragSelecting.current = false;
    if (!e.ctrlKey && !e.shiftKey) setSelectedItems([]);
    const rect = containerRef.current.getBoundingClientRect();
    setSelectionBox({
      startX: e.clientX - rect.left,
      startY: e.clientY - rect.top + containerRef.current.scrollTop,
      currentX: e.clientX - rect.left,
      currentY: e.clientY - rect.top + containerRef.current.scrollTop,
      initialSelected: e.ctrlKey ? [...selectedItems] : [],
    });
  };

  const handleMouseMove = (e) => {
    if (!selectionBox) return;
    const rect = containerRef.current.getBoundingClientRect();
    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top + containerRef.current.scrollTop;
    if (
      Math.abs(currentX - selectionBox.startX) > 5 ||
      Math.abs(currentY - selectionBox.startY) > 5
    ) {
      isDragSelecting.current = true;
    }
    setSelectionBox((prev) => ({ ...prev, currentX, currentY }));
    const left = Math.min(selectionBox.startX, currentX);
    const top = Math.min(selectionBox.startY, currentY);
    const width = Math.abs(currentX - selectionBox.startX);
    const height = Math.abs(currentY - selectionBox.startY);
    const newSelected = [];
    Object.keys(itemRefs.current).forEach((key) => {
      const el = itemRefs.current[key];
      if (!el) return;
      const itemRect = el.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();
      const itemLeft = itemRect.left - containerRect.left;
      const itemTop =
        itemRect.top - containerRect.top + containerRef.current.scrollTop;
      if (
        left < itemLeft + itemRect.width &&
        left + width > itemLeft &&
        top < itemTop + itemRect.height &&
        top + height > itemTop
      ) {
        newSelected.push(key);
      }
    });
    const merged = Array.from(
      new Set([...selectionBox.initialSelected, ...newSelected]),
    );
    setSelectedItems(merged);
  };

  const handleMouseUp = () => setSelectionBox(null);

  // Keyboard shortcuts
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (editingItem) {
        if (e.key === "Enter")
          newItemType ? finishCreateFolder() : finishRename();
        if (e.key === "Escape") {
          setEditingItem(null);
          setNewItemType(null);
        }
        return;
      }
      const target = e.target;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      )
        return;
      if (e.key === "Delete") handleDelete();
      if (e.ctrlKey && e.key === "c") handleCopy();
      if (e.ctrlKey && e.key === "x") handleCut();
      if (e.ctrlKey && e.key === "v") handlePaste();
      if ((e.ctrlKey || e.metaKey) && e.key === "a") {
        e.preventDefault();
        const allKeys = [
          ...folders
            .filter((f) => f.parent === currentFolder)
            .map((f) => f.key),
          ...(files[currentFolder] || []).map((f) => f.key),
        ];
        setSelectedItems(allKeys);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedItems,
    clipboard,
    currentFolder,
    folders,
    files,
    editingItem,
    newItemType,
    tempName,
  ]);

  // Context menu handling
  const handleContextMenu = (e, type, key) => {
    e.preventDefault();
    e.stopPropagation();
    if (type === "item") {
      if (!selectedItems.includes(key)) setSelectedItems([key]);
    } else if (type === "container") {
      if (
        e.target === containerRef.current ||
        e.target.className === "file-manager-content"
      )
        setSelectedItems([]);
    }
    setContextMenu({ x: e.clientX, y: e.clientY, type, key });
  };

  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  const renderItem = (item, type) => {
    const isSelected = selectedItems.includes(item.key);
    const isEditing = editingItem === item.key;
    const isImagePreview = type !== "folder" && isImageFile(item);
    const iconSize = viewMode === "grid" ? 48 : 24;
    const icon = isImagePreview ? (
      <div
        style={{
          width: iconSize,
          height: iconSize,
          borderRadius: 4,
          border: "1px solid #f0f0f0",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
          position: "relative",
          background: "#fafafa",
        }}
      >
        {previewStatus[item.key] !== "loaded" && <Spin size="small" />}
        {previewStatus[item.key] !== "error" && (
          <img
            src={getPreviewUrl(item.key)}
            alt={item.name}
            loading="lazy"
            onLoad={() => markPreviewLoaded(item.key)}
            onError={() => markPreviewError(item.key)}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: previewStatus[item.key] === "loaded" ? 1 : 0,
              transition: "opacity 0.2s ease",
            }}
          />
        )}
      </div>
    ) : type === "folder" ? (
      <FolderFilled
        style={{
          fontSize: iconSize,
          color: "var(--seg-accent-primary, #3f37c9)",
        }}
      />
    ) : (
      <FileOutlined style={{ fontSize: iconSize, color: "#555" }} />
    );
    return (
      <div
        key={item.key}
        ref={(el) => (itemRefs.current[item.key] = el)}
        draggable={!isEditing}
        onDragStart={(e) => handleDragStart(e, item.key, type)}
        onDragOver={type === "folder" ? handleDragOver : undefined}
        onDrop={type === "folder" ? (e) => handleDrop(e, item.key) : undefined}
        onContextMenu={(e) => handleContextMenu(e, "item", item.key)}
        onClick={(e) => {
          e.stopPropagation();
          if (e.ctrlKey) {
            setSelectedItems((prev) =>
              isSelected
                ? prev.filter((k) => k !== item.key)
                : [...prev, item.key],
            );
          } else if (e.shiftKey && selectedItems.length) {
            setSelectedItems((prev) => [...prev, item.key]);
          } else {
            setSelectedItems([item.key]);
          }
        }}
        onDoubleClick={() => {
          if (isEditing) return;
          if (type === "folder") handleNavigate(item.key);
          else handlePreview(item.key);
        }}
        style={{
          width: viewMode === "grid" ? 100 : "100%",
          padding: 8,
          margin: viewMode === "grid" ? 8 : 0,
          textAlign: viewMode === "grid" ? "center" : "left",
          cursor: "pointer",
          borderRadius: 4,
          backgroundColor: isSelected
            ? "var(--seg-selection-fill, rgba(63, 55, 201, 0.12))"
            : "transparent",
          border: isSelected
            ? "1px solid var(--seg-accent-primary, #3f37c9)"
            : "1px solid transparent",
          display: viewMode === "list" ? "flex" : "block",
          alignItems: "center",
          userSelect: "none",
        }}
      >
        <div
          style={{
            marginBottom: viewMode === "grid" ? 4 : 0,
            marginRight: viewMode === "list" ? 12 : 0,
            display: viewMode === "grid" ? "flex" : "block",
            justifyContent: viewMode === "grid" ? "center" : "flex-start",
            width: viewMode === "grid" ? "100%" : "auto",
          }}
        >
          {icon}
        </div>
        {isEditing ? (
          <Input
            ref={inputRef}
            size="small"
            value={tempName}
            onChange={(e) => setTempName(e.target.value)}
            onBlur={() => (newItemType ? finishCreateFolder() : finishRename())}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Enter")
                newItemType ? finishCreateFolder() : finishRename();
              if (e.key === "Escape") {
                setEditingItem(null);
                setNewItemType(null);
              }
            }}
            style={{ width: viewMode === "grid" ? "100%" : 300 }}
          />
        ) : (
          <div style={{ wordBreak: "break-word", fontSize: 12 }}>
            {item.title || item.name}
            {type === "folder" &&
              item.parent === "root" &&
              item.physical_path && (
                <span
                  style={{
                    display: "inline-block",
                    marginLeft: 6,
                    padding: "2px 6px",
                    fontSize: 10,
                    borderRadius: 10,
                    background: "var(--seg-accent-primary-soft, #f0efff)",
                    color: "var(--seg-accent-primary, #3f37c9)",
                    border:
                      "1px solid var(--seg-accent-primary-border, #c7c2ff)",
                  }}
                >
                  Mounted
                </span>
              )}
          </div>
        )}
      </div>
    );
  };

  const renderNewFolderPlaceholder = () => {
    if (newItemType !== "folder") return null;
    return (
      <div
        style={{
          width: viewMode === "grid" ? 100 : "100%",
          padding: 8,
          margin: viewMode === "grid" ? 8 : 0,
          textAlign: viewMode === "grid" ? "center" : "left",
          borderRadius: 4,
          border: "1px solid var(--seg-accent-primary, #3f37c9)",
          display: viewMode === "list" ? "flex" : "block",
          alignItems: "center",
        }}
      >
        <div
          style={{
            marginBottom: viewMode === "grid" ? 4 : 0,
            marginRight: viewMode === "list" ? 12 : 0,
            display: viewMode === "grid" ? "flex" : "block",
            justifyContent: viewMode === "grid" ? "center" : "flex-start",
            width: viewMode === "grid" ? "100%" : "auto",
          }}
        >
          <FolderFilled
            style={{
              fontSize: viewMode === "grid" ? 48 : 24,
              color: "var(--seg-accent-primary, #3f37c9)",
            }}
          />
        </div>
        <Input
          ref={inputRef}
          size="small"
          value={tempName}
          onChange={(e) => setTempName(e.target.value)}
          onBlur={finishCreateFolder}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") finishCreateFolder();
            if (e.key === "Escape") {
              setEditingItem(null);
              setNewItemType(null);
            }
          }}
          style={{ width: viewMode === "grid" ? "100%" : 300 }}
        />
      </div>
    );
  };

  const currentFolders = folders.filter((f) => f.parent === currentFolder);
  const currentFiles = files[currentFolder] || [];
  const suggestedProject =
    projectSuggestions.find((item) => item.recommended) || projectSuggestions[0];

  const renderProjectSuggestion = () => {
    if (!suggestedProject || currentFolder !== "root") {
      return null;
    }
    const profile = suggestedProject.profile || {};
    const counts = profile.counts || {};
    const shownRoles = Object.entries(PROJECT_ROLE_LABELS).filter(
      ([role]) => counts[role] > 0,
    );
    const missingRoles = profile.missing_roles || [];
    const pairedExample = profile.paired_examples?.[0];

    return (
      <div
        style={{
          margin: "10px 0 0",
          padding: "10px 12px",
          border: "1px solid #d6e4ff",
          borderRadius: 10,
          background: "#f8fbff",
          display: "flex",
          gap: 12,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 220, flex: "1 1 260px" }}>
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            Project setup: {suggestedProject.name}
          </div>
          <div style={{ color: "#5f6f89", fontSize: 12, marginTop: 2 }}>
            {profile.ready_for_smoke
              ? "Ready for image/label, checkpoint, prediction, and metric checks."
              : missingRoles.length
                ? `Missing detected ${missingRoles.join(", ")} role(s).`
                : suggestedProject.description}
          </div>
          {pairedExample && (
            <div
              style={{
                color: "#5f6f89",
                fontSize: 11,
                marginTop: 4,
                wordBreak: "break-word",
              }}
            >
              Pair: {pairedExample.image} -> {pairedExample.label}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {shownRoles.map(([role, label]) => (
            <span
              key={role}
              style={{
                borderRadius: 999,
                padding: "3px 8px",
                background: "#fff",
                border:
                  "1px solid var(--seg-accent-primary-border, #c7c2ff)",
                color: "var(--seg-accent-primary, #3f37c9)",
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              {counts[role]} {label}
            </span>
          ))}
        </div>
        <Button size="small" onClick={handleSuggestedProject}>
          {suggestedProject.already_mounted ? "Open" : "Mount"}
        </Button>
      </div>
    );
  };

  const getContextMenuItems = () => {
    if (contextMenu?.type === "container") {
      return [
        { key: "new_folder", label: "Create Folder", icon: <FolderFilled /> },
        { key: "upload", label: "Upload File...", icon: <UploadOutlined /> },
        {
          key: "mount_project",
          label: "Mount Project Directory...",
          icon: <FolderOpenOutlined />,
        },
      ];
    }
    const items = [];
    const selectedKey = selectedItems.length === 1 ? selectedItems[0] : null;
    const selectedFolder = selectedKey
      ? folders.find((f) => f.key === selectedKey)
      : null;
    const isMountedProjectFolder = Boolean(
      selectedFolder &&
      selectedFolder.parent === "root" &&
      selectedFolder.physical_path,
    );
    // Only show preview for files, not folders
    if (selectedItems.length === 1) {
      const isFolder = folders.some((f) => f.key === selectedKey);
      if (!isFolder) {
        items.push({ key: "preview", label: "Preview", icon: <EyeOutlined /> });
      }
    }
    if (isMountedProjectFolder) {
      items.push({
        key: "unmount_project",
        label: "Unmount Project",
        danger: true,
        icon: <FolderOpenOutlined />,
      });
    }
    if (selectedItems.length === 1) {
      const selectedFile = Object.values(files)
        .flat()
        .find((f) => f.key === selectedKey);
      const selectedFolder = folders.find((f) => f.key === selectedKey);
      const hasPhysicalPath =
        (selectedFile &&
          selectedFile.physical_path &&
          selectedFile.physical_path.startsWith("/")) ||
        (selectedFolder &&
          selectedFolder.physical_path &&
          selectedFolder.physical_path.startsWith("/"));
      if (hasPhysicalPath) {
        items.push({
          key: "reveal_in_finder",
          label: "Open in Finder",
          icon: <FolderOpenOutlined />,
        });
      }
    }
    items.push(
      {
        key: "rename",
        label: "Rename",
        icon: <FileTextOutlined />,
        disabled: selectedItems.length > 1,
      },
      {
        key: "copy",
        label: `Copy${selectedItems.length > 1 ? ` (${selectedItems.length})` : ""}`,
        icon: <FileOutlined />,
      },
      {
        key: "delete",
        label: `Delete${selectedItems.length > 1 ? ` (${selectedItems.length})` : ""}`,
        danger: true,
        icon: <FileOutlined />,
      },
      { type: "divider" },
      { key: "properties", label: "Properties", icon: <FileTextOutlined /> },
    );
    return items;
  };

  const handleUploadClick = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.onchange = async (e) => {
      const filesSelected = Array.from(e.target.files);
      for (const file of filesSelected) {
        const form = new FormData();
        form.append("file", file);
        form.append("path", currentFolder);
        try {
          const res = await apiClient.post(`/files/upload`, form, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          const newFile = res.data;
          setFiles((prev) => ({
            ...prev,
            [currentFolder]: [
              ...(prev[currentFolder] || []),
              {
                key: String(newFile.id),
                name: newFile.name,
                size: newFile.size,
                type: newFile.type,
              },
            ],
          }));
          message.success(`${file.name} uploaded`);
        } catch (err) {
          console.error("Upload error", err);
          message.error(`Failed to upload ${file.name}`);
        }
      }
    };
    input.click();
  };

  const handleMountProjectDirectory = async () => {
    try {
      const selectedDirectory = await openLocalFile({
        properties: ["openDirectory"],
      });
      if (!selectedDirectory) return;

      // Mount builds a stable project index now; later this same flow can point to
      // cloud-backed project storage while keeping picker + workflow behavior unchanged.
      const res = await apiClient.post(
        "/files/mount",
        {
          directory_path: selectedDirectory,
          destination_path: "root",
        },
        { withCredentials: true },
      );

      await fetchFolderContents("root", { force: true });
      await loadProjectSuggestions();
      if (res?.data?.mounted_root_id) {
        const mountedRootId = String(res.data.mounted_root_id);
        await fetchFolderContents(mountedRootId, { force: true });
        handleNavigate(mountedRootId);
      }
      message.success(res?.data?.message || "Project directory mounted.");
    } catch (err) {
      console.error("Mount directory error", err);
      message.error("Failed to mount project directory");
    }
  };

  const handleSuggestedProject = async () => {
    const suggestion =
      projectSuggestions.find((item) => item.recommended) || projectSuggestions[0];
    if (!suggestion) {
      message.info("No suggested local project is available.");
      return;
    }
    if (suggestion.already_mounted && suggestion.mounted_root_id) {
      const mountedRootId = String(suggestion.mounted_root_id);
      await fetchFolderContents(mountedRootId, { force: true });
      handleNavigate(mountedRootId);
      await registerProjectWithWorkflow(suggestion);
      message.success(`${suggestion.name} is already mounted.`);
      return;
    }
    try {
      const res = await apiClient.post(
        "/files/mount",
        {
          directory_path: suggestion.directory_path,
          destination_path: "root",
          mount_name: suggestion.name,
        },
        { withCredentials: true },
      );
      await fetchFolderContents("root", { force: true });
      await loadProjectSuggestions();
      if (res?.data?.mounted_root_id) {
        const mountedRootId = String(res.data.mounted_root_id);
        await fetchFolderContents(mountedRootId, { force: true });
        handleNavigate(mountedRootId);
      }
      await registerProjectWithWorkflow(suggestion);
      message.success(res?.data?.message || `${suggestion.name} mounted.`);
    } catch (error) {
      console.error("Suggested project mount error", error);
      message.error(`Failed to mount ${suggestion.name}`);
    }
  };

  const registerProjectWithWorkflow = async (suggestion) => {
    if (!workflowContext?.updateWorkflow) {
      return;
    }
    const patch = buildWorkflowPatchFromProjectSuggestion(suggestion);
    if (!Object.keys(patch).length) {
      return;
    }
    try {
      await workflowContext.updateWorkflow(patch);
      await workflowContext.appendEvent?.({
        actor: "user",
        event_type: "dataset.loaded",
        stage: workflowContext.workflow?.stage || "setup",
        summary: `Registered project roles from ${suggestion.name}.`,
        payload: {
          source: "file_management_project_suggestion",
          suggestion_id: suggestion.id,
          ...patch,
        },
      });
    } catch (error) {
      console.warn("Failed to register mounted project with workflow", error);
    }
  };

  const handleResetWorkspace = () => {
    Modal.confirm({
      title: "Reset workspace?",
      content:
        "This clears indexed mounted projects and uploaded app files for the current workspace. Source project directories on disk are preserved.",
      okText: "Continue",
      okButtonProps: { danger: true },
      cancelText: "Cancel",
      onOk: async () => {
        let confirmText = "";
        let finalConfirmModal = null;

        finalConfirmModal = Modal.confirm({
          title: "Final confirmation required",
          content: (
            <div>
              <div style={{ marginBottom: 8 }}>
                Type <strong>RESET</strong> to clear this workspace.
              </div>
              <Input
                placeholder='Type "RESET"'
                onChange={(e) => {
                  confirmText = e.target.value;
                  if (finalConfirmModal) {
                    finalConfirmModal.update({
                      okButtonProps: {
                        danger: true,
                        disabled: confirmText.trim() !== "RESET",
                      },
                    });
                  }
                }}
              />
            </div>
          ),
          okText: "Reset Workspace",
          okButtonProps: { danger: true, disabled: true },
          cancelText: "Cancel",
          onOk: async () => {
            if (confirmText.trim() !== "RESET") {
              return;
            }

            try {
              const res = await apiClient.delete("/files/workspace", {
                withCredentials: true,
              });
              await context.resetFileState();
              resetLocalFileCache();
              await fetchFolderContents("root", { force: true });
              handleNavigate("root");
              setSelectedItems([]);
              message.success(
                `Workspace reset. Removed ${res?.data?.deleted_count ?? 0} indexed item(s).`,
              );
            } catch (err) {
              console.error("Workspace reset error", err);
              message.error("Failed to reset workspace");
            }
          },
        });
      },
    });
  };

  const workspaceMenuItems = [
    {
      key: "reset_workspace",
      label: "Reset Workspace",
      icon: <DeleteOutlined />,
      danger: true,
    },
  ];

  const handleUnmountProject = async (folderKey) => {
    const mountedFolder = folders.find((f) => f.key === folderKey);
    if (!mountedFolder) return;
    Modal.confirm({
      title: "Unmount project?",
      content:
        "This removes the indexed project from the app only. Source files on disk are not deleted.",
      okText: "Unmount",
      okButtonProps: { danger: true },
      cancelText: "Cancel",
      onOk: async () => {
        try {
          const shouldReturnToRoot =
            currentFolder === folderKey ||
            isFolderWithinSubtree(foldersRef.current, folderKey, currentFolder);
          await apiClient.delete(`/files/unmount/${folderKey}`, {
            withCredentials: true,
          });
          removeFolderSubtrees([folderKey]);
          await fetchFolderContents("root", { force: true });
          if (shouldReturnToRoot) {
            handleNavigate("root");
          }
          message.success("Project unmounted.");
        } catch (err) {
          console.error("Unmount error", err);
          message.error("Failed to unmount project");
        }
      },
    });
  };

  const handleRevealInFinder = async (key) => {
    const item =
      folders.find((f) => f.key === key) ||
      Object.values(files)
        .flat()
        .find((f) => f.key === key);
    if (!item || !item.physical_path || !item.physical_path.startsWith("/")) {
      message.warning("This item is not linked to a local file.");
      return;
    }
    try {
      await revealInFinder(item.physical_path);
    } catch (err) {
      console.error("Reveal in Finder error", err);
      message.error("Failed to open in Finder");
    }
  };

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "row",
        position: "relative",
      }}
    >
      {isSidebarVisible && (
        <>
          <FileTreeSidebar
            folders={folders}
            files={files}
            currentFolder={currentFolder}
            onSelect={handleNavigate}
            onLoadFolder={fetchFolderContents}
            onDrop={(info) => {
              const dropKey = info.node.key;
              const dragKey = info.dragNode.key;
              // Handle folder-to-folder drop (sidebar internal) or file-to-folder drop
              // Note: Ant Design Tree drag/drop is complex.
              // For simplicity, we assume dropping ONTO a folder (dropPosition === 0)
              if (!info.dropToGap && dropKey.startsWith("folder-")) {
                const targetFolderId = dropKey.replace("folder-", "");
                const sourceId = dragKey.replace(/^(folder-|file-)/, "");
                // Reuse existing drop logic if possible, or call API directly
                // We need to know if source is file or folder
                const isSourceFolder = dragKey.startsWith("folder-");

                // Call existing drop handler logic
                // We need to mock the event object or refactor handleDrop to accept keys
                // Refactoring handleDrop is better but for now let's just call the API
                const moveItem = async () => {
                  try {
                    const item = isSourceFolder
                      ? folders.find((f) => f.key === sourceId)
                      : Object.values(files)
                          .flat()
                          .find((f) => f.key === sourceId);

                    if (!item) return;

                    await apiClient.put(
                      `/files/${sourceId}`,
                      {
                        name: item.title || item.name,
                        path: targetFolderId,
                      },
                      { withCredentials: true },
                    );

                    if (isSourceFolder) {
                      setFolders((prev) =>
                        prev.map((f) =>
                          f.key === sourceId
                            ? { ...f, parent: targetFolderId }
                            : f,
                        ),
                      );
                    } else {
                      setFiles((prev) => {
                        const sourceFolder = Object.keys(prev).find((fk) =>
                          prev[fk].some((f) => f.key === sourceId),
                        );
                        if (!sourceFolder) return prev;
                        const fileObj = prev[sourceFolder].find(
                          (f) => f.key === sourceId,
                        );
                        const newSource = prev[sourceFolder].filter(
                          (f) => f.key !== sourceId,
                        );
                        const newTarget = [
                          ...(prev[targetFolderId] || []),
                          fileObj,
                        ];
                        return {
                          ...prev,
                          [sourceFolder]: newSource,
                          [targetFolderId]: newTarget,
                        };
                      });
                    }
                    message.success(
                      `Moved to ${folders.find((f) => f.key === targetFolderId)?.title}`,
                    );
                  } catch (err) {
                    console.error("Sidebar drop error", err);
                    message.error("Failed to move item");
                  }
                };
                moveItem();
              }
            }}
            onContextMenu={(e, node) => {
              e.preventDefault();
              // Determine if it's a folder or file
              const key = node.key;
              const id = key.replace(/^(folder-|file-)/, "");

              // Select the item
              setSelectedItems([id]);

              // Show context menu
              setContextMenu({
                x: e.clientX,
                y: e.clientY,
                type: "item",
                key: id,
              });
            }}
            loadedParents={loadedParents}
            loadingParents={loadingParents}
            expandedKeys={expandedFolders}
            onExpand={setExpandedFolders}
            width={sidebarWidth}
          />
          <div
            onMouseDown={startResizing}
            style={{
              width: 4,
              cursor: "col-resize",
              backgroundColor: "#f0f0f0",
              height: "100%",
              flexShrink: 0,
              marginRight: 8,
            }}
          />
        </>
      )}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          height: "100%",
          overflow: "hidden",
        }}
        onClick={(e) => {
          if (isDragSelecting.current) {
            isDragSelecting.current = false;
            return;
          }
          setSelectedItems([]);
          setContextMenu(null);
        }}
        onContextMenu={(e) => handleContextMenu(e, "container")}
      >
        {/* Toolbar & Breadcrumbs */}
        <div
          style={{
            padding: "12px 0",
            borderBottom: "1px solid #f0f0f0",
            display: "flex",
            gap: 16,
            alignItems: "center",
          }}
        >
          <Button
            icon={<LayoutOutlined />}
            onClick={() => setIsSidebarVisible(!isSidebarVisible)}
            title={isSidebarVisible ? "Hide Sidebar" : "Show Sidebar"}
          />
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={handleUp}
            disabled={currentFolder === "root"}
            size="small"
          />
          <Breadcrumb style={{ flex: 1 }}>
            {getBreadcrumbs().map((f) => (
              <Breadcrumb.Item
                key={f.key}
                onClick={() => handleNavigate(f.key)}
                style={{ cursor: "pointer" }}
              >
                {f.key === "root" ? "Projects" : f.title}
              </Breadcrumb.Item>
            ))}
          </Breadcrumb>
          <Button
            icon={viewMode === "grid" ? <BarsOutlined /> : <AppstoreOutlined />}
            onClick={() => setViewMode(viewMode === "grid" ? "list" : "grid")}
            title={
              viewMode === "grid"
                ? "Switch to List View"
                : "Switch to Grid View"
            }
          />
          <Button
            icon={<FolderOpenOutlined />}
            onClick={handleMountProjectDirectory}
          >
            Mount Project
          </Button>
          <Button
            onClick={handleSuggestedProject}
            disabled={projectSuggestions.length === 0}
            title={
              projectSuggestions.length
                ? projectSuggestions[0].description
                : "No suggested local projects found"
            }
          >
            {projectSuggestions.some((item) => item.already_mounted)
              ? "Open Test Project"
              : "Mount Test Project"}
          </Button>
          <Dropdown
            menu={{
              items: workspaceMenuItems,
              onClick: ({ key }) => {
                if (key === "reset_workspace") {
                  handleResetWorkspace();
                }
              },
            }}
            trigger={["click"]}
          >
            <Button icon={<MoreOutlined />} title="More file actions" />
          </Dropdown>
        </div>
        {renderProjectSuggestion()}

        {/* Content Area */}
        <div
          ref={containerRef}
          className="file-manager-content"
          style={{
            flex: 1,
            overflow: "auto",
            display: "flex",
            flexWrap: "wrap",
            alignContent: "flex-start",
            position: "relative",
            flexDirection: viewMode === "list" ? "column" : "row",
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onDragOver={handleDragOver}
          onDrop={(e) => handleDrop(e, currentFolder)}
        >
          {loadingParents.includes(currentFolder) && (
            <div
              style={{
                width: "100%",
                marginTop: 64,
                display: "flex",
                justifyContent: "center",
              }}
            >
              <Spin size="large" />
            </div>
          )}
          {!loadingParents.includes(currentFolder) &&
            currentFolders.length === 0 &&
            currentFiles.length === 0 &&
            !newItemType && (
            <div
              style={{ width: "100%", marginTop: 64, pointerEvents: "none" }}
            >
              <Empty description="Empty Folder" />
            </div>
          )}
          {currentFolders.map((f) => renderItem(f, "folder"))}
          {renderNewFolderPlaceholder()}
          {currentFiles.map((f) => renderItem(f, "file"))}
          {selectionBox && (
            <div
              style={{
                position: "absolute",
                left: Math.min(selectionBox.startX, selectionBox.currentX),
                top: Math.min(selectionBox.startY, selectionBox.currentY),
                width: Math.abs(selectionBox.currentX - selectionBox.startX),
                height: Math.abs(selectionBox.currentY - selectionBox.startY),
                backgroundColor:
                  "var(--seg-selection-fill, rgba(63, 55, 201, 0.12))",
                border: "1px solid var(--seg-accent-primary, #3f37c9)",
                pointerEvents: "none",
                zIndex: 100,
              }}
            />
          )}
        </div>

        {/* Context Menu */}
        {contextMenu && (
          <div
            style={{
              position: "fixed",
              top: contextMenu.y,
              left: contextMenu.x,
              zIndex: 1000,
              background: "#fff",
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              borderRadius: 4,
              border: "1px solid #f0f0f0",
            }}
          >
            <Menu
              selectable={false}
              onClick={({ key }) => {
                setContextMenu(null);
                if (key === "new_folder") startCreateFolder();
                if (key === "upload") handleUploadClick();
                if (key === "mount_project") handleMountProjectDirectory();
                if (key === "unmount_project")
                  handleUnmountProject(contextMenu.key);
                if (key === "reveal_in_finder")
                  handleRevealInFinder(contextMenu.key);
                if (key === "rename") {
                  const item =
                    folders.find((f) => f.key === contextMenu.key) ||
                    (files[currentFolder] || []).find(
                      (f) => f.key === contextMenu.key,
                    );
                  startRename(contextMenu.key, item.title || item.name);
                }
                if (key === "copy")
                  handleCopy(
                    selectedItems.length > 0
                      ? selectedItems
                      : [contextMenu.key],
                  );
                if (key === "delete")
                  handleDelete(
                    selectedItems.length > 0
                      ? selectedItems
                      : [contextMenu.key],
                  );
                if (key === "preview") handlePreview(contextMenu.key);
                if (key === "properties")
                  handleProperties(
                    selectedItems.length > 0
                      ? selectedItems
                      : [contextMenu.key],
                  );
              }}
              items={getContextMenuItems()}
            />
          </div>
        )}

        {/* Preview Modal */}
        <Modal
          title={previewFile?.name}
          open={!!previewFile}
          onCancel={() => setPreviewFile(null)}
          footer={null}
          width={800}
        >
          {previewFile && (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                minHeight: 300,
              }}
            >
              {previewFile.type?.startsWith("image") ? (
                <Image
                  src="https://via.placeholder.com/600x400?text=Image+Preview+Placeholder"
                  alt={previewFile.name}
                  style={{ maxWidth: "100%", maxHeight: 600 }}
                />
              ) : (
                <div
                  style={{
                    padding: 20,
                    background: "#f5f5f5",
                    width: "100%",
                    borderRadius: 8,
                  }}
                >
                  <pre style={{ whiteSpace: "pre-wrap" }}>
                    {previewFile.name === "readme.txt"
                      ? "This is a dummy text file content.\n\nIn a real app, this would fetch the file content from the server."
                      : "Preview not available for this file type."}
                  </pre>
                </div>
              )}
            </div>
          )}
        </Modal>

        {/* Properties Modal */}
        <Modal
          title="Properties"
          open={!!propertiesData}
          onCancel={() => setPropertiesData(null)}
          footer={[
            <Button
              key="close"
              type="primary"
              onClick={() => setPropertiesData(null)}
            >
              Close
            </Button>,
          ]}
          width={500}
        >
          {propertiesData && propertiesData.type === "single" && (
            <div style={{ padding: "16px 0" }}>
              <div
                style={{
                  marginBottom: 16,
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                {propertiesData.isFolder ? (
                  <FolderFilled
                    style={{
                      fontSize: 48,
                      color: "var(--seg-accent-primary, #3f37c9)",
                    }}
                  />
                ) : (
                  <FileOutlined style={{ fontSize: 48, color: "#555" }} />
                )}
                <div>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: "bold",
                      marginBottom: 4,
                    }}
                  >
                    {propertiesData.name}
                  </div>
                  <div style={{ color: "#888", fontSize: 12 }}>
                    {propertiesData.isFolder ? "Folder" : "File"}
                  </div>
                </div>
              </div>
              <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 16 }}>
                <div
                  style={{
                    marginBottom: 12,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontWeight: 500 }}>Type:</span>
                  <span>{propertiesData.fileType}</span>
                </div>
                <div
                  style={{
                    marginBottom: 12,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontWeight: 500 }}>Size:</span>
                  <span>{propertiesData.size}</span>
                </div>
                {propertiesData.isMountedFolder && (
                  <>
                    <div
                      style={{
                        marginBottom: 12,
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ fontWeight: 500 }}>Folders:</span>
                      <span>{propertiesData.folderCount}</span>
                    </div>
                    <div
                      style={{
                        marginBottom: 12,
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ fontWeight: 500 }}>Files:</span>
                      <span>{propertiesData.fileCount}</span>
                    </div>
                  </>
                )}
                <div
                  style={{
                    marginBottom: 12,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontWeight: 500 }}>Created:</span>
                  <span>{propertiesData.created}</span>
                </div>
                <div
                  style={{ display: "flex", justifyContent: "space-between" }}
                >
                  <span style={{ fontWeight: 500 }}>Modified:</span>
                  <span>{propertiesData.modified}</span>
                </div>
              </div>
            </div>
          )}
          {propertiesData && propertiesData.type === "multiple" && (
            <div style={{ padding: "16px 0" }}>
              <div
                style={{ fontSize: 16, fontWeight: "bold", marginBottom: 16 }}
              >
                Selection Summary
              </div>
              <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 16 }}>
                <div
                  style={{
                    marginBottom: 12,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontWeight: 500 }}>Total Items:</span>
                  <span>{propertiesData.totalCount}</span>
                </div>
                <div
                  style={{
                    marginBottom: 12,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontWeight: 500 }}>Folders:</span>
                  <span>{propertiesData.folderCount}</span>
                </div>
                <div
                  style={{
                    marginBottom: 12,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontWeight: 500 }}>Files:</span>
                  <span>{propertiesData.fileCount}</span>
                </div>
                <div
                  style={{ display: "flex", justifyContent: "space-between" }}
                >
                  <span style={{ fontWeight: 500 }}>Total Size:</span>
                  <span>{propertiesData.totalSize}</span>
                </div>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </div>
  );
}

export default FilesManager;
