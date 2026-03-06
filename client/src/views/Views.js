import React, { useState, useEffect, useRef, useCallback } from "react";
import { Layout, Menu, Button, Drawer } from "antd";
import {
  FolderOpenOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
  BugOutlined,
  MessageOutlined,
  BarChartOutlined,
  ProjectOutlined,
} from "@ant-design/icons";
import FilesManager from "./FilesManager";
import Visualization from "./Visualization";
import ModelTraining from "./ModelTraining";
import ModelInference from "./ModelInference";
import Monitoring from "./Monitoring";
<<<<<<< HEAD
import MaskProofreading from "./MaskProofreading";
=======
import ProofReading from "./ProofReading";
import WormErrorHandling from "./WormErrorHandling";
import ProjectManager from "./project-manager/ProjectManager";
import WorkflowSelector from "../components/WorkflowSelector";
>>>>>>> c648179 (feat:  annotation management system)
import Chatbot from "../components/Chatbot";

const { Content } = Layout;

const MODULE_ITEMS = [
  { label: "File Management", key: "files", icon: <FolderOpenOutlined /> },
  { label: "Visualization", key: "visualization", icon: <EyeOutlined /> },
  { label: "Model Training", key: "training", icon: <ExperimentOutlined /> },
  {
    label: "Model Inference",
    key: "inference",
    icon: <ThunderboltOutlined />,
  },
  { label: "Tensorboard", key: "monitoring", icon: <DashboardOutlined /> },
  {
    label: "Mask Proofreading",
    key: "mask-proofreading",
    icon: <BugOutlined />,
  },
];

function Views() {
  const [current, setCurrent] = useState("files");
  const [visitedTabs, setVisitedTabs] = useState(new Set(["files"]));
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(560);
  const isResizing = useRef(false);

  const [viewers, setViewers] = useState([]);
  const [isInferring, setIsInferring] = useState(false);

<<<<<<< HEAD
=======
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
    {
      label: "Project Manager",
      key: "project-manager",
      icon: <ProjectOutlined />,
    },
  ];

  const items = allItems.filter((item) => visibleTabs.has(item.key));

>>>>>>> c648179 (feat:  annotation management system)
  const onClick = (e) => {
    setCurrent(e.key);
    setVisitedTabs((prev) => new Set(prev).add(e.key));
  };

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
          items={MODULE_ITEMS}
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
<<<<<<< HEAD
        {renderTabContent("mask-proofreading", <MaskProofreading />)}
=======
        {renderTabContent("synanno", <ProofReading />)}
        {renderTabContent("worm-error-handling", <WormErrorHandling />)}
        {renderTabContent("project-manager", <ProjectManager />)}
>>>>>>> c648179 (feat:  annotation management system)
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
