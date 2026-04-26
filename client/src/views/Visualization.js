import React, { useState } from "react";
import { Button, Tabs, Input, Space, Typography, message } from "antd";
import {
  ArrowRightOutlined,
  InboxOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { apiClient, getNeuroglancerViewer } from "../api";
import UnifiedFileInput from "../components/UnifiedFileInput";
import StageHeader from "../components/workflow/StageHeader";
import { useWorkflow } from "../contexts/WorkflowContext";

const { Title } = Typography;

function Visualization(props) {
  const { viewers, setViewers } = props;
  const workflowContext = useWorkflow();
  const [activeKey, setActiveKey] = useState(
    viewers.length > 0 ? viewers[0].key : null,
  );

  // Input states
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [scales, setScales] = useState("30,6,6");
  const [isLoading, setIsLoading] = useState(false);

  const handleImageChange = (value) => {
    console.log(`selected image:`, value);
    setCurrentImage(value);
  };

  const handleLabelChange = (value) => {
    console.log(`selected label:`, value);
    setCurrentLabel(value);
  };

  const handleInputScales = (event) => {
    setScales(event.target.value);
  };

  // Helper to get path string from potential object
  const getPath = (val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.path || "";
  };

  // Helper to get display string from potential object
  const getDisplay = (val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.display || val.path || "";
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

  const validateManagedUploadSelection = async (value, role) => {
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
  };

  const loadViewer = async (imageValue, labelValue, scalesValue) => {
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

      const scalesArray = scalesValue.split(",").map(Number);
      const viewerId =
        imagePath + (labelPath || "") + JSON.stringify(scalesArray);

      let updatedViewers = viewers;
      const exists = viewers.find((viewer) => viewer.key === viewerId);

      if (exists) {
        updatedViewers = viewers.filter((viewer) => viewer.key !== viewerId);
      }

      const res = await getNeuroglancerViewer(
        imagePath,
        labelPath,
        scalesArray,
        workflowContext?.workflow?.id,
      );

      const newViewers = [
        ...updatedViewers,
        {
          key: viewerId,
          title: getViewerTitle(imageValue, labelValue),
          viewer: res,
        },
      ];

      setViewers(newViewers);
      setActiveKey(viewerId);
    } catch (e) {
      console.log(e);
      message.error(e?.message || "Failed to load viewer");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchNeuroglancerViewer = async () => {
    await loadViewer(currentImage, currentLabel, scales);
  };

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
          viewer: viewer.viewer + "?refresh=" + new Date().getTime(),
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
              placeholder="30,6,6"
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
