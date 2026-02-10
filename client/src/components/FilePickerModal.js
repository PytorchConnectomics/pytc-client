import React, { useState, useEffect } from "react";
import { Modal, List, Breadcrumb, Button, Spin, message } from "antd";
import {
  FolderFilled,
  FileOutlined,
  ArrowLeftOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { apiClient } from "../api";

const HIDDEN_SYSTEM_FILES = new Set([
  "workflow_preference.json",
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
]);

const FilePickerModal = ({
  visible,
  onCancel,
  onSelect,
  title = "Select File",
  selectionType = "file",
}) => {
  const [currentPath, setCurrentPath] = useState("root");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [previewStatus, setPreviewStatus] = useState({});
  const [onlyImages, setOnlyImages] = useState(false);
  const previewBaseUrl =
    apiClient.defaults.baseURL || "http://localhost:4242";

  // Refactored fetch to get all files once
  const [allData, setAllData] = useState([]);

  useEffect(() => {
    if (visible) {
      setCurrentPath("root");
      setOnlyImages(false);
      loadAllData();
    }
  }, [visible]);

  const loadAllData = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/files");
      setAllData(res.data);
    } catch (error) {
      message.error("Failed to load files");
    } finally {
      setLoading(false);
    }
  };

  // Derive items for current view
  useEffect(() => {
    const filtered = allData.filter((f) => {
      const nameLower = String(f.name || "").toLowerCase();
      if (!f.is_folder && HIDDEN_SYSTEM_FILES.has(nameLower)) return false;
      if (currentPath === "root") return f.path === "root" || !f.path;
      return String(f.path) === currentPath;
    });

    const filteredByType = onlyImages
      ? filtered.filter((f) => f.is_folder || isImageFile(f))
      : filtered;

    filteredByType.sort((a, b) => {
      if (a.is_folder === b.is_folder) return a.name.localeCompare(b.name);
      return a.is_folder ? -1 : 1;
    });

    setItems(filteredByType);
  }, [currentPath, allData, onlyImages]);

  const getParentPath = () => {
    if (currentPath === "root") return null;
    const currentFolderObj = allData.find((f) => String(f.id) === currentPath);
    return currentFolderObj ? currentFolderObj.path || "root" : "root";
  };

  const goUp = () => {
    const parent = getParentPath();
    if (parent) setCurrentPath(parent);
  };

  const getBreadcrumbs = () => {
    const parts = [];
    let curr = currentPath;
    while (curr && curr !== "root") {
      const folder = allData.find((f) => String(f.id) === curr);
      if (folder) {
        parts.unshift({ id: String(folder.id), name: folder.name });
        curr = folder.path;
      } else {
        break;
      }
    }
    parts.unshift({ id: "root", name: "Projects" });
    return parts;
  };

  const constructFullPath = (item) => {
    if (!item) return "";
    if (item.path === "root" || !item.path) return item.name;

    const parts = [item.name];
    let currParentId = item.path;

    // Safety break to prevent infinite loops
    let attempts = 0;
    while (currParentId && currParentId !== "root" && attempts < 100) {
      const parent = allData.find((f) => String(f.id) === currParentId);
      if (parent) {
        parts.unshift(parent.name);
        currParentId = parent.path;
      } else {
        break;
      }
      attempts++;
    }
    return parts.join("/");
  };

  const handleSelectCurrentDirectory = () => {
    // Construct path for current directory
    if (currentPath === "root") {
      onSelect({ name: "", path: "root", is_folder: true, logical_path: "" }); // Root
      return;
    }
    const currentFolder = allData.find((f) => String(f.id) === currentPath);
    if (currentFolder) {
      const fullPath = constructFullPath(currentFolder);
      onSelect({ ...currentFolder, logical_path: fullPath });
    }
  };

  const handleUploadFromLocal = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.onchange = async (event) => {
      const selectedFiles = Array.from(event.target.files || []);
      if (!selectedFiles.length) return;
      let uploaded = 0;
      for (const file of selectedFiles) {
        const form = new FormData();
        form.append("file", file);
        form.append("path", currentPath);
        try {
          await apiClient.post("/files/upload", form, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          uploaded += 1;
        } catch (error) {
          console.error("Failed to upload file from picker:", error);
          message.error(`Failed to upload ${file.name}`);
        }
      }
      if (uploaded > 0) {
        message.success(
          `Uploaded ${uploaded} file${uploaded > 1 ? "s" : ""} to this folder`,
        );
        await loadAllData();
      }
    };
    input.click();
  };

  const isImageFile = (item) => {
    if (!item || item.is_folder) return false;
    if (item.type && item.type.startsWith("image/")) return true;
    const ext = `.${String(item.name || "").split(".").pop()}`.toLowerCase();
    return IMAGE_EXTENSIONS.has(ext);
  };

  const getPreviewUrl = (item) =>
    `${previewBaseUrl}/files/preview/${item.id}`;

  const markPreviewLoaded = (id) => {
    setPreviewStatus((prev) => ({ ...prev, [id]: "loaded" }));
  };

  const markPreviewError = (id) => {
    setPreviewStatus((prev) => ({ ...prev, [id]: "error" }));
  };

  return (
    <Modal
      title={title}
      open={visible}
      onCancel={onCancel}
      footer={
        selectionType === "directory" || selectionType === "fileOrDirectory" ? (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              padding: "10px 16px",
            }}
          >
            <Button onClick={onCancel} style={{ marginRight: 8 }}>
              Cancel
            </Button>
            <Button type="primary" onClick={handleSelectCurrentDirectory}>
              Select Current Directory
            </Button>
          </div>
        ) : null
      }
      width={600}
      bodyStyle={{ padding: 0 }}
    >
      <div
        style={{
          padding: "12px",
          borderBottom: "1px solid #f0f0f0",
          display: "flex",
          alignItems: "center",
        }}
      >
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={goUp}
          disabled={currentPath === "root"}
          style={{ marginRight: "12px" }}
        />
        <Breadcrumb>
          {getBreadcrumbs().map((b) => (
            <Breadcrumb.Item key={b.id}>
              <a onClick={() => setCurrentPath(b.id)}>{b.name}</a>
            </Breadcrumb.Item>
          ))}
        </Breadcrumb>
        <Button
          icon={<UploadOutlined />}
          onClick={handleUploadFromLocal}
          style={{ marginLeft: "auto" }}
        >
          Upload from Local
        </Button>
        <Button
          type={onlyImages ? "primary" : "default"}
          onClick={() => setOnlyImages((prev) => !prev)}
          style={{ marginLeft: 8 }}
        >
          Images Only
        </Button>
      </div>

      <div style={{ height: "400px", overflow: "auto" }}>
        {loading ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              padding: "40px",
            }}
          >
            <Spin />
          </div>
        ) : (
          <List
            dataSource={items}
            renderItem={(item) => (
              <List.Item
                style={{ cursor: "pointer", padding: "8px 16px" }}
                className="file-picker-item"
                onClick={() => {
                  if (item.is_folder) {
                    setCurrentPath(String(item.id));
                  } else {
                    if (selectionType === "file") {
                      const fullPath = constructFullPath(item);
                      onSelect({ ...item, logical_path: fullPath });
                    }
                  }
                }}
                actions={[
                  (selectionType === "file" ||
                    selectionType === "fileOrDirectory") &&
                    !item.is_folder && (
                      <Button
                        type="link"
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          const fullPath = constructFullPath(item);
                          onSelect({ ...item, logical_path: fullPath });
                        }}
                      >
                        Select
                      </Button>
                    ),
                  (selectionType === "directory" ||
                    selectionType === "fileOrDirectory") &&
                    item.is_folder && (
                      <Button
                        type="link"
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          const fullPath = constructFullPath(item);
                          onSelect({ ...item, logical_path: fullPath });
                        }}
                      >
                        Select
                      </Button>
                    ),
                ]}
              >
                <List.Item.Meta
                  avatar={
                    item.is_folder ? (
                      <FolderFilled
                        style={{ color: "#1890ff", fontSize: "20px" }}
                      />
                    ) : isImageFile(item) ? (
                      <div
                        style={{
                          width: 32,
                          height: 32,
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
                        {previewStatus[item.id] !== "loaded" && (
                          <Spin size="small" />
                        )}
                        {previewStatus[item.id] !== "error" && (
                          <img
                            src={getPreviewUrl(item)}
                            alt={item.name}
                            loading="lazy"
                            onLoad={() => markPreviewLoaded(item.id)}
                            onError={() => markPreviewError(item.id)}
                            style={{
                              position: "absolute",
                              inset: 0,
                              width: "100%",
                              height: "100%",
                              objectFit: "cover",
                              opacity:
                                previewStatus[item.id] === "loaded" ? 1 : 0,
                              transition: "opacity 0.2s ease",
                            }}
                          />
                        )}
                      </div>
                    ) : (
                      <FileOutlined style={{ fontSize: "20px" }} />
                    )
                  }
                  title={
                    <span>
                      {item.name}
                      {item.is_folder &&
                        (item.path === "root" || !item.path) &&
                        item.physical_path && (
                          <span
                            style={{
                              marginLeft: 8,
                              padding: "2px 6px",
                              fontSize: 10,
                              borderRadius: 10,
                              background: "#f0f5ff",
                              color: "#2f54eb",
                              border: "1px solid #adc6ff",
                            }}
                          >
                            Mounted
                          </span>
                        )}
                    </span>
                  }
                  description={item.size ? item.size : null}
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  );
};

export default FilePickerModal;
