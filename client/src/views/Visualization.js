import React, {
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Button,
  Tabs,
  Input,
  Space,
  Typography,
  message,
  notification,
} from "antd";
import {
  ArrowRightOutlined,
  InboxOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { apiClient, getNeuroglancerViewer } from "../api";
import UnifiedFileInput from "../components/UnifiedFileInput";
import StageHeader from "../components/workflow/StageHeader";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";
import { logClientEvent } from "../logging/appEventLog";

const { Title } = Typography;

const formatScales = (value) => {
  if (!value) return "";
  if (Array.isArray(value)) return value.join(",");
  return String(value);
};

const getPath = (val) => {
  if (!val) return "";
  if (typeof val === "string") return val;
  return val.path || "";
};

const getDisplay = (val) => {
  if (!val) return "";
  if (typeof val === "string") return val;
  return val.display || val.path || "";
};

const looksLikeVolumeFile = (value) => {
  const path = getPath(value).toLowerCase();
  return /\.(?:h5|hdf5|tif|tiff|npy|npz|nii|nii\.gz|mrc|mrcs)$/.test(path);
};

const getViewerTitle = (imageValue, labelValue) => {
  const getImageName = (val) => {
    const display = getDisplay(val);
    if (!display) return "";
    const parts = display.split(/[/\\]/);
    return parts[parts.length - 1];
  };

  return (
    getImageName(imageValue) +
    (labelValue ? " & " + getImageName(labelValue) : "")
  );
};

const waitForViewerLayout = () =>
  new Promise((resolve) => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        window.setTimeout(resolve, 250);
      });
    });
  });

const appendRefreshParam = (url) => {
  if (!url) return url;
  const hashIndex = url.indexOf("#");
  const base = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
  const hash = hashIndex >= 0 ? url.slice(hashIndex) : "";
  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}refresh=${Date.now()}${hash}`;
};

const isMixedContentUrl = (url) => {
  if (typeof window === "undefined" || window.location.protocol !== "https:") {
    return false;
  }
  try {
    return new URL(url, window.location.href).protocol === "http:";
  } catch {
    return false;
  }
};

function Visualization(props) {
  const { viewers, setViewers } = props;
  const workflowContext = useWorkflow();
  const appContext = useContext(AppContext);
  const globalImage = appContext?.currentImage || null;
  const globalLabel = appContext?.currentLabel || null;
  const globalScales = appContext?.visualizationScales || "";
  const workflow = workflowContext?.workflow;
  const observedVolumeSets =
    workflow?.metadata?.project_observation?.volume_sets;
  const observedVolumeSet = Array.isArray(observedVolumeSets)
    ? observedVolumeSets.find((item) => item?.is_current) ||
      observedVolumeSets[0]
    : null;
  const workflowImage =
    observedVolumeSet?.image_path ||
    (looksLikeVolumeFile(workflow?.image_path) ? workflow.image_path : null);
  const workflowLabel =
    observedVolumeSet?.label_path ||
    (looksLikeVolumeFile(workflow?.label_path) ? workflow.label_path : null);
  const workflowScales =
    workflow?.metadata?.visualization_scales ||
    workflow?.metadata?.project_context?.voxel_size_nm ||
    null;
  const hydratedWorkflowRef = useRef(null);
  const handledRuntimeActionRef = useRef(null);
  const viewerRefreshTimersRef = useRef([]);
  const [activeKey, setActiveKey] = useState(
    viewers.length > 0 ? viewers[0].key : null,
  );

  // Input states
  const [currentImage, setCurrentImage] = useState(
    globalImage || workflowImage || null,
  );
  const [currentLabel, setCurrentLabel] = useState(
    globalLabel || workflowLabel || null,
  );
  const [scales, setScales] = useState(
    formatScales(workflowScales) || formatScales(globalScales) || "",
  );
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const workflowId = workflow?.id;
    if (!workflowId || hydratedWorkflowRef.current === workflowId) {
      return;
    }
    const isWorkflowChange = hydratedWorkflowRef.current !== null;
    hydratedWorkflowRef.current = workflowId;

    if ((isWorkflowChange || !globalImage) && workflowImage) {
      setCurrentImage(workflowImage);
      appContext?.setCurrentImage?.(workflowImage);
    }
    if ((isWorkflowChange || !globalLabel) && workflowLabel) {
      setCurrentLabel(workflowLabel);
      appContext?.setCurrentLabel?.(workflowLabel);
    }
    if ((isWorkflowChange || !globalImage) && workflowScales) {
      const nextScales = formatScales(workflowScales);
      setScales(nextScales);
      appContext?.setVisualizationScales?.(nextScales);
    }
  }, [
    appContext,
    globalImage,
    globalLabel,
    workflow?.id,
    workflowImage,
    workflowLabel,
    workflowScales,
  ]);

  useEffect(() => {
    return () => {
      viewerRefreshTimersRef.current.forEach((timerId) => {
        window.clearTimeout(timerId);
      });
      viewerRefreshTimersRef.current = [];
    };
  }, []);

  const handleImageChange = (value) => {
    setCurrentImage(value);
    appContext?.setCurrentImage?.(value);
  };

  const handleLabelChange = (value) => {
    setCurrentLabel(value);
    appContext?.setCurrentLabel?.(value);
  };

  useEffect(() => {
    const nextImage = globalImage || workflowImage || null;
    if (nextImage !== currentImage) {
      setCurrentImage(nextImage);
    }
  }, [globalImage, workflowImage, currentImage]);

  useEffect(() => {
    const nextLabel = globalLabel || workflowLabel || null;
    if (nextLabel !== currentLabel) {
      setCurrentLabel(nextLabel);
    }
  }, [globalLabel, workflowLabel, currentLabel]);

  useEffect(() => {
    const nextScales = globalImage
      ? formatScales(globalScales || workflowScales)
      : formatScales(workflowScales) || formatScales(globalScales);
    if (nextScales !== scales) {
      setScales(nextScales);
    }
  }, [globalImage, globalScales, workflowScales, scales]);

  const handleInputScales = (event) => {
    const nextScales = event.target.value;
    setScales(nextScales);
    appContext?.setVisualizationScales?.(nextScales);
  };

  const parseScalesInput = useCallback((value) => {
    const parts = (String(value || "").match(/-?\d+(?:\.\d+)?/g) || []).map(
      Number,
    );
    if (
      parts.length < 3 ||
      parts.slice(0, 3).some((part) => !Number.isFinite(part) || part <= 0)
    ) {
      return null;
    }
    return parts.slice(0, 3);
  }, []);

  const validateManagedUploadSelection = useCallback(async (value, role) => {
    const selectedPath = getPath(value);
    if (!selectedPath || !selectedPath.startsWith("uploads/")) {
      return true;
    }

    const response = await apiClient.get("/files");
    const exists = (response.data || []).some(
      (item) => !item.is_folder && item.physical_path === selectedPath,
    );
    if (exists) {
      return true;
    }

    if (role === "image") {
      setCurrentImage(null);
    } else {
      setCurrentLabel(null);
    }
    message.error(
      `The selected ${role} file is no longer present in app uploads. Please re-select or re-upload it.`,
    );
    return false;
  }, []);

  const loadViewer = useCallback(
    async (imageValue, labelValue, scalesValue, options = {}) => {
      const imagePath = getPath(imageValue);
      const labelPath = getPath(labelValue);

      if (!imagePath) {
        message.error("Please select an image");
        return;
      }

      setIsLoading(true);
      try {
        const imageSelectionOk = await validateManagedUploadSelection(
          imageValue,
          "image",
        );
        if (!imageSelectionOk) {
          return;
        }
        const labelSelectionOk = await validateManagedUploadSelection(
          labelValue,
          "label",
        );
        if (!labelSelectionOk) {
          return;
        }

        const scalesArray = parseScalesInput(scalesValue);
        if (!scalesArray) {
          message.error(
            "Enter voxel scales as z,y,x nanometers before opening the viewer.",
          );
          return;
        }
        const viewerId =
          imagePath + (labelPath || "") + JSON.stringify(scalesArray);

        let updatedViewers = viewers;
        const exists = viewers.find((viewer) => viewer.key === viewerId);

        if (exists) {
          updatedViewers = viewers.filter((viewer) => viewer.key !== viewerId);
        }

        const viewerResult = await getNeuroglancerViewer(
          imagePath,
          labelPath,
          scalesArray,
          workflowContext?.workflow?.id,
        );
        const viewerUrl =
          typeof viewerResult === "string"
            ? viewerResult
            : viewerResult?.url || viewerResult?.neuroglancer_url || "";

        if (!viewerUrl) {
          throw new Error("Viewer did not return a Neuroglancer URL.");
        }
        logClientEvent("visualization_viewer_url_received", {
          level: "INFO",
          message: "Received Neuroglancer viewer URL",
          source: "visualization",
          data: {
            viewerUrl,
            imagePath,
            labelPath,
            scales: scalesArray,
            workflowId: workflowContext?.workflow?.id || null,
            requestedImagePath: viewerResult?.requested_image_path || imagePath,
            requestedLabelPath: viewerResult?.requested_label_path || labelPath,
            resolvedImagePath: viewerResult?.image_path || null,
            resolvedLabelPath: viewerResult?.label_path || null,
          },
        });
        if (isMixedContentUrl(viewerUrl)) {
          logClientEvent("visualization_viewer_mixed_content_blocked", {
            level: "ERROR",
            message: "Blocked insecure Neuroglancer viewer URL on HTTPS page",
            source: "visualization",
            data: {
              viewerUrl,
              pageUrl: window.location.href,
              imagePath,
              labelPath,
              scales: scalesArray,
              workflowId: workflowContext?.workflow?.id || null,
            },
          });
          throw new Error(
            "Viewer URL is insecure for this HTTPS page. The server must expose Neuroglancer through HTTPS.",
          );
        }

        const resolvedImagePath = viewerResult?.image_path;
        const resolvedLabelPath = viewerResult?.label_path;
        const pairQuestion = viewerResult?.pair_question;
        if (resolvedImagePath && resolvedImagePath !== imagePath) {
          setCurrentImage(resolvedImagePath);
          appContext?.setCurrentImage?.(resolvedImagePath);
        }
        if (resolvedLabelPath && resolvedLabelPath !== labelPath) {
          setCurrentLabel(resolvedLabelPath);
          appContext?.setCurrentLabel?.(resolvedLabelPath);
        }
        if (pairQuestion) {
          const pairCount = viewerResult?.pair_discovery?.pair_count || 0;
          const notificationKey = `volume-pairs-${viewerId}`;
          notification.info({
            key: notificationKey,
            message: `Found ${pairCount} image/segmentation pairs`,
            description:
              "I opened the first pair. You can use the progress tracker to review which volumes are proofread, draft, or missing masks.",
            duration: 12,
            btn: (
              <Space size={8}>
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    notification.close(notificationKey);
                    workflowContext?.runClientEffects?.({
                      navigate_to: "project-progress",
                      refresh_project_progress: true,
                    });
                  }}
                >
                  Open Progress
                </Button>
                <Button
                  size="small"
                  onClick={() => {
                    notification.close(notificationKey);
                    workflowContext?.runClientEffects?.({
                      navigate_to: "files",
                    });
                  }}
                >
                  Show Files
                </Button>
              </Space>
            ),
          });
        }

        const newViewers = [
          ...updatedViewers,
          {
            key: viewerId,
            title: getViewerTitle(
              resolvedImagePath || imageValue,
              resolvedLabelPath || labelValue,
            ),
            viewer: viewerUrl,
          },
        ];

        setViewers(newViewers);
        setActiveKey(viewerId);
        logClientEvent("visualization_viewer_mounted", {
          level: "INFO",
          message: "Mounted Neuroglancer iframe",
          source: "visualization",
          data: {
            viewerId,
            viewerUrl,
            title: getViewerTitle(
              resolvedImagePath || imageValue,
              resolvedLabelPath || labelValue,
            ),
            imagePath: resolvedImagePath || imagePath,
            labelPath: resolvedLabelPath || labelPath,
            scales: scalesArray,
            workflowId: workflowContext?.workflow?.id || null,
          },
        });
        if (options.refreshAfterMount) {
          const timerId = window.setTimeout(() => {
            setViewers((currentViewers) =>
              currentViewers.map((viewer) =>
                viewer.key === viewerId
                  ? { ...viewer, viewer: appendRefreshParam(viewer.viewer) }
                  : viewer,
              ),
            );
          }, options.refreshAfterMount);
          viewerRefreshTimersRef.current.push(timerId);
        }
      } catch (error) {
        console.error("Failed to load Neuroglancer viewer", error);
        logClientEvent("visualization_viewer_load_failed", {
          level: "ERROR",
          message: error?.message || "Failed to load Neuroglancer viewer",
          source: "visualization",
          data: {
            imagePath,
            labelPath,
            scalesValue,
            workflowId: workflowContext?.workflow?.id || null,
            error,
          },
        });
        message.error(error?.message || "Failed to load viewer");
      } finally {
        setIsLoading(false);
      }
    },
    [
      appContext,
      parseScalesInput,
      setViewers,
      validateManagedUploadSelection,
      viewers,
      workflowContext,
    ],
  );

  const fetchNeuroglancerViewer = async () => {
    await loadViewer(currentImage, currentLabel, scales);
  };

  useEffect(() => {
    const action = workflowContext?.pendingRuntimeAction;
    if (!action || action.kind !== "load_visualization") return;
    if (handledRuntimeActionRef.current === action.id) return;
    handledRuntimeActionRef.current = action.id;

    const overrideScales = formatScales(action.overrides?.visualizationScales);
    const imageValue =
      action.overrides?.visualizationImagePath || currentImage || globalImage;
    const labelValue =
      action.overrides?.visualizationLabelPath || currentLabel || globalLabel;
    const scalesValue = overrideScales || scales;
    if (overrideScales) {
      setScales(overrideScales);
      appContext?.setVisualizationScales?.(overrideScales);
    }
    if (imageValue) {
      setCurrentImage(imageValue);
      appContext?.setCurrentImage?.(imageValue);
    }
    if (labelValue) {
      setCurrentLabel(labelValue);
      appContext?.setCurrentLabel?.(labelValue);
    }

    waitForViewerLayout()
      .then(() => {
        return loadViewer(imageValue, labelValue, scalesValue, {
          refreshAfterMount: 800,
        });
      })
      .finally(() => {
        workflowContext?.consumeRuntimeAction?.(action.id);
      });
  }, [
    appContext,
    currentImage,
    currentLabel,
    globalImage,
    globalLabel,
    loadViewer,
    scales,
    workflowContext,
  ]);

  const handleEdit = (targetKey, action) => {
    if (action === "remove") {
      remove(targetKey);
    }
  };

  const remove = (targetKey) => {
    let newActiveKey = activeKey;
    let lastIndex = -1;
    viewers.forEach((item, i) => {
      if (item.key === targetKey) {
        lastIndex = i - 1;
      }
    });
    const newPanes = viewers.filter((item) => item.key !== targetKey);
    if (newPanes.length && newActiveKey === targetKey) {
      if (lastIndex >= 0) {
        newActiveKey = newPanes[lastIndex].key;
      } else {
        newActiveKey = newPanes[0].key;
      }
    }
    setViewers(newPanes);
    setActiveKey(newActiveKey);
  };

  const handleChange = (newActiveKey) => {
    setActiveKey(newActiveKey);
  };

  const refreshViewer = (key) => {
    const updatedViewers = viewers.map((viewer) => {
      if (viewer.key === key) {
        return {
          ...viewer,
          viewer: appendRefreshParam(viewer.viewer),
        };
      }
      return viewer;
    });
    setViewers(updatedViewers);
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ marginBottom: 12 }}>
        <StageHeader
          stage="visualization"
          title="Visualization"
          subtitle="Inspect image and label volumes before routing failures into inference or proofreading."
        />
      </div>
      {/* Input Section */}
      <div
        style={{
          padding: "16px",
          background: "#f5f5f5",
          borderRadius: "8px",
          marginBottom: "16px",
        }}
      >
        <Space wrap align="end">
          <div>
            <Title level={5} style={{ margin: "0 0 8px 0" }}>
              Image
            </Title>
            <UnifiedFileInput
              placeholder="Please select or input image path"
              onChange={handleImageChange}
              value={currentImage}
              style={{ width: "200px" }}
            />
          </div>

          <div>
            <Title level={5} style={{ margin: "0 0 8px 0" }}>
              Label
            </Title>
            <UnifiedFileInput
              placeholder="Please select or input label path"
              onChange={handleLabelChange}
              value={currentLabel}
              style={{ width: "200px" }}
            />
          </div>

          <div>
            <Title level={5} style={{ margin: "0 0 8px 0" }}>
              Scales (z,y,x)
            </Title>
            <Input
              placeholder="z,y,x nm"
              value={scales}
              onChange={handleInputScales}
              style={{ width: "150px" }}
            />
          </div>

          <Button
            type="primary"
            onClick={fetchNeuroglancerViewer}
            icon={<ArrowRightOutlined />}
            loading={isLoading}
          >
            Visualize
          </Button>
        </Space>
      </div>

      {/* Viewers Section */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {viewers.length > 0 ? (
          <div style={{ height: "calc(100vh - 250px)" }}>
            <Tabs
              className="visualization-viewer-tabs"
              closeIcon
              type="editable-card"
              tabPosition="bottom"
              hideAdd
              onEdit={handleEdit}
              activeKey={activeKey}
              onChange={handleChange}
              style={{ height: "100%" }}
              items={viewers.map((viewer) => ({
                label: (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <span>{viewer.title}</span>
                    <Button
                      type="link"
                      icon={<ReloadOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        refreshViewer(viewer.key);
                      }}
                      style={{ paddingInline: 4 }}
                    />
                  </span>
                ),
                key: viewer.key,
                children: (
                  <div
                    style={{
                      height: "100%",
                      overflow: "hidden",
                      borderRadius: 8,
                      background: "#000",
                    }}
                  >
                    <iframe
                      title="Viewer Display"
                      width="100%"
                      height="800"
                      frameBorder="0"
                      scrolling="no"
                      src={viewer.viewer}
                      onLoad={() =>
                        logClientEvent("visualization_iframe_loaded", {
                          level: "INFO",
                          message: "Neuroglancer iframe load event",
                          source: "visualization",
                          data: {
                            viewerKey: viewer.key,
                            viewerUrl: viewer.viewer,
                            activeKey,
                          },
                        })
                      }
                      onError={(event) =>
                        logClientEvent("visualization_iframe_error", {
                          level: "ERROR",
                          message: "Neuroglancer iframe error event",
                          source: "visualization",
                          data: {
                            viewerKey: viewer.key,
                            viewerUrl: viewer.viewer,
                            activeKey,
                            eventType: event?.type,
                          },
                        })
                      }
                      style={{
                        width: "100%",
                        height: "100%",
                        display: "block",
                      }}
                    />
                  </div>
                ),
              }))}
            />
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "40px", color: "#999" }}>
            <InboxOutlined style={{ fontSize: "48px", marginBottom: "16px" }} />
            <p>Select an image and click Visualize to get started</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Visualization;
