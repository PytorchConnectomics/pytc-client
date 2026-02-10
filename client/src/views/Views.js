import React, { useState, useEffect, useRef, useCallback } from "react";
import { Layout, Menu, Button, Drawer } from "antd";
import {
  FolderOpenOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
  BugOutlined,
  ApartmentOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import FilesManager from "./FilesManager";
import Visualization from "./Visualization";
import ModelTraining from "./ModelTraining";
import ModelInference from "./ModelInference";
import Monitoring from "./Monitoring";
import ProofReading from "./ProofReading";
import WormErrorHandling from "./WormErrorHandling";
import WorkflowSelector from "../components/WorkflowSelector";
import Chatbot from "../components/Chatbot";

const { Content } = Layout;

function Views() {
  // State
  const [current, setCurrent] = useState("files");
  const [visibleTabs, setVisibleTabs] = useState(new Set(["files"]));
  const [visitedTabs, setVisitedTabs] = useState(new Set(["files"]));
  const [workflowModalVisible, setWorkflowModalVisible] = useState(true);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(380);
  const isResizing = useRef(false);

  // Lifted state from Workspace
  const [viewers, setViewers] = useState([]);
  const [isInferring, setIsInferring] = useState(false);

  const allItems = [
    { label: "File Management", key: "files", icon: <FolderOpenOutlined /> },
    { label: "Visualization", key: "visualization", icon: <EyeOutlined /> },
    { label: "Model Training", key: "training", icon: <ExperimentOutlined /> },
    {
      label: "Model Inference",
      key: "inference",
      icon: <ThunderboltOutlined />,
    },
    { label: "Tensorboard", key: "monitoring", icon: <DashboardOutlined /> },
    { label: "SynAnno", key: "synanno", icon: <ApartmentOutlined /> },
    {
      label: "Worm Error Handling",
      key: "worm-error-handling",
      icon: <BugOutlined />,
    },
  ];

  const items = allItems.filter((item) => visibleTabs.has(item.key));

  const onClick = (e) => {
    setCurrent(e.key);
    setVisitedTabs((prev) => new Set(prev).add(e.key));
  };

  // Helper to activate tabs and set valid current
  const applyModes = (modes) => {
    const modeList = Array.isArray(modes) ? modes : [modes];
    if (modeList.length === 0) return;

    setVisitedTabs((prev) => {
      const next = new Set(prev);
      modeList.forEach((m) => next.add(m));
      return next;
    });
    setVisibleTabs((prev) => {
      const next = new Set(prev);
      modeList.forEach((m) => next.add(m));
      return next;
    });

    // Switch to first selected tab, or 'files' if included, or keep current if valid
    if (modeList.includes("files")) {
      setCurrent("files");
    } else {
      setCurrent(modeList[0]);
    }
  };

  const handleWorkflowSelect = (modes) => {
    setWorkflowModalVisible(false);
    applyModes(modes);
  };

  // IPC Listener
  useEffect(() => {
    let ipcRenderer;
    try {
      ipcRenderer = window.require("electron").ipcRenderer;
    } catch (e) {
      return;
    }

    const handleToggleTab = (_event, key, checked) => {
      setVisibleTabs((prev) => {
        const newSet = new Set(prev);
        if (checked) {
          newSet.add(key);
        } else {
          newSet.delete(key);
          if (current === key) setCurrent("files");
        }
        return newSet;
      });
    };

    const handleChangeViews = () => {
      // User clicked "Change Views"
      setWorkflowModalVisible(true);
    };

    ipcRenderer.on("toggle-tab", handleToggleTab);
    ipcRenderer.on("change-views", handleChangeViews);

    return () => {
      ipcRenderer.removeListener("toggle-tab", handleToggleTab);
      ipcRenderer.removeListener("change-views", handleChangeViews);
    };
  }, [current]);

  const startResizing = useCallback((e) => {
    isResizing.current = true;
    e.preventDefault();
  }, []);

  const stopResizing = useCallback(() => {
    isResizing.current = false;
  }, []);

  const resize = useCallback((e) => {
    if (isResizing.current) {
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= 280 && newWidth <= 800) {
        setChatWidth(newWidth);
      }
    }
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", resize);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [resize, stopResizing]);

  const renderTabContent = (key, component) => {
    if (!visitedTabs.has(key)) return null;
    return (
      <div
        style={{ display: current === key ? "block" : "none", height: "100%" }}
      >
        {component}
      </div>
    );
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <WorkflowSelector
        visible={workflowModalVisible}
        onSelect={handleWorkflowSelect}
        onCancel={() => {
          setWorkflowModalVisible(false);
        }}
      />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          background: "#fff",
          paddingRight: 16,
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Menu
          onClick={onClick}
          selectedKeys={[current]}
          mode="horizontal"
          items={items}
          style={{
            lineHeight: "64px",
            paddingLeft: "16px",
            flex: 1,
            borderBottom: "none",
          }}
        />
        <Button
          type="primary"
          shape="circle"
          icon={<MessageOutlined />}
          onClick={() => setIsChatOpen(true)}
        />
      </div>
      <Content
        style={{
          padding: "24px",
          height: "calc(100vh - 64px)",
          overflow: "auto",
        }}
      >
        {renderTabContent("files", <FilesManager />)}
        {renderTabContent(
          "visualization",
          <Visualization viewers={viewers} setViewers={setViewers} />,
        )}
        {renderTabContent("training", <ModelTraining />)}
        {renderTabContent("monitoring", <Monitoring />)}
        {renderTabContent(
          "inference",
          <ModelInference
            isInferring={isInferring}
            setIsInferring={setIsInferring}
          />,
        )}
        {renderTabContent("synanno", <ProofReading />)}
        {renderTabContent("worm-error-handling", <WormErrorHandling />)}
      </Content>
      <Drawer
        placement="right"
        open={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        width={chatWidth}
        mask={false}
        closable={false}
        destroyOnClose
        styles={{ header: { display: "none" }, body: { padding: 0 } }}
      >
        <div
          onMouseDown={startResizing}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: "4px",
            cursor: "ew-resize",
            backgroundColor: "transparent",
            zIndex: 10,
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = "#1890ff")
          }
          onMouseLeave={(e) =>
            !isResizing.current &&
            (e.currentTarget.style.backgroundColor = "transparent")
          }
        />
        <Chatbot onClose={() => setIsChatOpen(false)} />
      </Drawer>
    </Layout>
  );
}

export default Views;
