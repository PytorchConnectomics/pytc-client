import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Modal,
  List,
  Breadcrumb,
  Button,
  Spin,
  message,
  Progress,
  Result,
  Empty,
} from "antd";
import {
  FolderFilled,
  FileOutlined,
  ArrowLeftOutlined,
  UploadOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { apiClient } from "../api";
import { normalizeApiError } from "../errors/apiError";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";

const FILE_PAGE_SIZE = 100;

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

const FilePickerModal = ({
  visible,
  onCancel,
  onSelect,
  title = "Select File",
  selectionType = "file",
}) => {
  const [currentPath, setCurrentPath] = useState("root");
  const [breadcrumbs, setBreadcrumbs] = useState([
    { id: "root", name: "Projects", item: null },
  ]);
  const [previewStatus, setPreviewStatus] = useState({});
  const [onlyImages, setOnlyImages] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const scrollRef = useRef(null);
  const queryClient = useQueryClient();
  const previewBaseUrl = apiClient.defaults.baseURL || "http://localhost:4242";

  const filesQuery = useInfiniteQuery({
    queryKey: ["files", "picker", currentPath, { onlyImages }],
    enabled: visible,
    initialPageParam: 0,
    queryFn: async ({ pageParam, signal }) => {
      const response = await apiClient.get("/files", {
        params: {
          parent: currentPath,
          offset: pageParam,
          limit: FILE_PAGE_SIZE,
          volume_only: onlyImages,
        },
        signal,
      });
      if (Array.isArray(response.data)) {
        return {
          items: response.data,
          total: response.data.length,
          offset: 0,
          limit: response.data.length || FILE_PAGE_SIZE,
          has_more: false,
        };
      }
      return response.data;
    },
    getNextPageParam: (page) =>
      page?.has_more
        ? Number(page.offset || 0) + Number(page.limit || 0)
        : null,
  });

  const allItems = useMemo(
    () => filesQuery.data?.pages.flatMap((page) => page.items || []) || [],
    [filesQuery.data],
  );
  const items = useMemo(() => {
    const visibleItems = allItems.filter((item) => {
      const nameLower = String(item.name || "").toLowerCase();
      return item.is_folder || !HIDDEN_SYSTEM_FILES.has(nameLower);
    });
    visibleItems.sort((a, b) => {
      if (a.is_folder === b.is_folder) return a.name.localeCompare(b.name);
      return a.is_folder ? -1 : 1;
    });
    return visibleItems;
  }, [allItems]);
  const loadError = useMemo(
    () => (filesQuery.isError ? normalizeApiError(filesQuery.error) : null),
    [filesQuery.error, filesQuery.isError],
  );

  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 64,
    overscan: 8,
    initialRect: { width: 568, height: 400 },
  });
  const virtualRows = rowVirtualizer.getVirtualItems();

  useEffect(() => {
    if (visible) {
      setCurrentPath("root");
      setBreadcrumbs([{ id: "root", name: "Projects", item: null }]);
      setOnlyImages(false);
      setPreviewStatus({});
      setUploadProgress(null);
    }
  }, [visible]);

  useEffect(() => {
    if (!visible) {
      queryClient.cancelQueries({ queryKey: ["files", "picker"] });
    }
  }, [queryClient, visible]);

  useEffect(() => {
    const lastRow = virtualRows[virtualRows.length - 1];
    if (
      lastRow &&
      lastRow.index >= items.length - 8 &&
      filesQuery.hasNextPage &&
      !filesQuery.isFetchingNextPage
    ) {
      filesQuery.fetchNextPage();
    }
  }, [filesQuery, items.length, virtualRows]);

  useEffect(() => {
    if (loadError) message.error(loadError.message);
  }, [loadError]);

  const getParentPath = () => {
    if (currentPath === "root") return null;
    return breadcrumbs[breadcrumbs.length - 2]?.id || "root";
  };

  const goUp = () => {
    const parent = getParentPath();
    if (parent) {
      setCurrentPath(parent);
      setBreadcrumbs((current) => current.slice(0, -1));
    }
  };

  const openFolder = (item) => {
    const id = String(item.id);
    setCurrentPath(id);
    setBreadcrumbs((current) => [...current, { id, name: item.name, item }]);
    scrollRef.current?.scrollTo({ top: 0 });
  };

  const constructFullPath = (item) => {
    if (!item) return "";
    return [...breadcrumbs.slice(1).map((part) => part.name), item.name].join(
      "/",
    );
  };

  const handleSelectCurrentDirectory = () => {
    // Construct path for current directory
    if (currentPath === "root") {
      onSelect({ name: "", path: "root", is_folder: true, logical_path: "" }); // Root
      return;
    }
    const currentFolder = breadcrumbs[breadcrumbs.length - 1];
    if (currentFolder?.item) {
      const fullPath = breadcrumbs
        .slice(1)
        .map((part) => part.name)
        .join("/");
      onSelect({ ...currentFolder.item, logical_path: fullPath });
    }
  };

  const handleUploadFromLocal = () => {
    if (uploading) return;
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.onchange = async (event) => {
      const selectedFiles = Array.from(event.target.files || []);
      if (!selectedFiles.length) return;
      let uploaded = 0;
      let uploadedBytes = 0;
      const totalBytes = selectedFiles.reduce(
        (sum, file) => sum + (file.size || 0),
        0,
      );

      setUploading(true);
      try {
        for (const [index, file] of selectedFiles.entries()) {
          const form = new FormData();
          form.append("file", file);
          form.append("path", currentPath);
          const bytesBeforeFile = uploadedBytes;
          setUploadProgress({
            currentFile: file.name,
            index: index + 1,
            total: selectedFiles.length,
            percent: totalBytes
              ? Math.round((bytesBeforeFile / totalBytes) * 100)
              : 0,
          });
          try {
            await apiClient.post("/files/upload", form, {
              headers: { "Content-Type": "multipart/form-data" },
              onUploadProgress: (progressEvent) => {
                const loadedForFile = Math.min(
                  progressEvent.loaded || 0,
                  file.size || progressEvent.loaded || 0,
                );
                const percent = totalBytes
                  ? Math.min(
                      99,
                      Math.round(
                        ((bytesBeforeFile + loadedForFile) / totalBytes) * 100,
                      ),
                    )
                  : 0;
                setUploadProgress({
                  currentFile: file.name,
                  index: index + 1,
                  total: selectedFiles.length,
                  percent,
                });
              },
            });
            uploaded += 1;
            uploadedBytes += file.size || 0;
          } catch (error) {
            console.error("Failed to upload file from picker:", error);
            message.error(`Failed to upload ${file.name}`);
          }
        }
        setUploadProgress((current) =>
          current ? { ...current, percent: 100 } : current,
        );
        if (uploaded > 0) {
          message.success(
            `Uploaded ${uploaded} file${uploaded > 1 ? "s" : ""} to this folder`,
          );
          await filesQuery.refetch();
        }
      } finally {
        setUploading(false);
        setTimeout(() => setUploadProgress(null), 900);
      }
    };
    input.click();
  };

  const isImageFile = (item) => {
    if (!item || item.is_folder) return false;
    if (item.type && item.type.startsWith("image/")) return true;
    const name = String(item.name || "").toLowerCase();
    const ext = `.${name.split(".").pop()}`;
    return IMAGE_EXTENSIONS.has(ext) || name.endsWith(".nii.gz");
  };

  const getPreviewUrl = (item) => `${previewBaseUrl}/files/preview/${item.id}`;

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
            <Button
              type="primary"
              onClick={handleSelectCurrentDirectory}
              disabled={uploading}
            >
              Use Current Folder
            </Button>
          </div>
        ) : null
      }
      width={600}
      styles={{ body: { padding: 0 } }}
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
        <Breadcrumb
          items={breadcrumbs.map((breadcrumb, index) => ({
            key: breadcrumb.id,
            title: (
              <Button
                type="link"
                size="small"
                onClick={() => {
                  setCurrentPath(breadcrumb.id);
                  setBreadcrumbs((current) => current.slice(0, index + 1));
                }}
                style={{ padding: 0 }}
              >
                {breadcrumb.name}
              </Button>
            ),
          }))}
        />
        <Button
          icon={<UploadOutlined />}
          onClick={handleUploadFromLocal}
          disabled={uploading}
          style={{ marginLeft: "auto" }}
        >
          {uploading ? "Uploading..." : "Upload from Local"}
        </Button>
        <Button
          type={onlyImages ? "primary" : "default"}
          onClick={() => setOnlyImages((prev) => !prev)}
          style={{ marginLeft: 8 }}
        >
          Volume files
        </Button>
      </div>
      {uploadProgress && (
        <div
          style={{
            padding: "10px 16px",
            borderBottom: "1px solid #f0f0f0",
            background: "#fbfbfa",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              fontSize: 12,
              color: "#6b7280",
              marginBottom: 4,
            }}
          >
            <span>
              Uploading {uploadProgress.index}/{uploadProgress.total}:{" "}
              {uploadProgress.currentFile}
            </span>
            <span>{uploadProgress.percent}%</span>
          </div>
          <Progress
            percent={uploadProgress.percent}
            size="small"
            status={uploadProgress.percent >= 100 ? "success" : "active"}
            showInfo={false}
          />
        </div>
      )}

      <div ref={scrollRef} style={{ height: "400px", overflow: "auto" }}>
        {filesQuery.isPending ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              padding: "40px",
            }}
          >
            <Spin />
          </div>
        ) : loadError ? (
          <Result
            status="error"
            title="Files unavailable"
            subTitle={loadError.message}
            extra={
              loadError.retryable ? (
                <Button
                  type="primary"
                  icon={<ReloadOutlined />}
                  onClick={() => filesQuery.refetch()}
                >
                  Try again
                </Button>
              ) : null
            }
          />
        ) : items.length === 0 ? (
          <Empty
            description={
              onlyImages
                ? "No volume files in this folder"
                : "No files in this folder"
            }
            style={{ marginTop: 96 }}
          />
        ) : (
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              position: "relative",
              width: "100%",
            }}
          >
            {virtualRows.map((virtualRow) => {
              const item = items[virtualRow.index];
              return (
                <div
                  key={item.id}
                  data-index={virtualRow.index}
                  ref={rowVirtualizer.measureElement}
                  style={{
                    left: 0,
                    position: "absolute",
                    top: 0,
                    transform: `translateY(${virtualRow.start}px)`,
                    width: "100%",
                  }}
                >
                  <List.Item
                    style={{ cursor: "pointer", padding: "8px 16px" }}
                    className="file-picker-item"
                    onClick={() => {
                      if (item.is_folder) {
                        openFolder(item);
                      } else {
                        if (selectionType === "file") {
                          const fullPath = constructFullPath(item);
                          onSelect({ ...item, logical_path: fullPath });
                        }
                      }
                    }}
                    actions={[
                      item.is_folder && (
                        <Button
                          type="link"
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            openFolder(item);
                          }}
                        >
                          Open
                        </Button>
                      ),
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
                            Select file
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
                            Use folder
                          </Button>
                        ),
                    ]}
                  >
                    <List.Item.Meta
                      avatar={
                        item.is_folder ? (
                          <FolderFilled
                            style={{
                              color: "var(--seg-accent-primary, #3f37c9)",
                              fontSize: "20px",
                            }}
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
                                  background:
                                    "var(--seg-accent-primary-soft, #f0efff)",
                                  color: "var(--seg-accent-primary, #3f37c9)",
                                  border:
                                    "1px solid var(--seg-accent-primary-border, #c7c2ff)",
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
                </div>
              );
            })}
            {filesQuery.isFetchingNextPage && (
              <div
                style={{
                  bottom: 12,
                  left: 0,
                  position: "sticky",
                  textAlign: "center",
                  width: "100%",
                }}
              >
                <Spin size="small" />
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};

export default FilePickerModal;
