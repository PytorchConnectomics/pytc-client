import React, { useState, useEffect, useRef, useCallback } from "react";
import { Layout, Menu, Button, Drawer, message } from "antd";
import {
  FolderOpenOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
  BugOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import FilesManager from "./FilesManager";
import Visualization from "./Visualization";
import ModelTraining from "./ModelTraining";
import ModelInference from "./ModelInference";
import Monitoring from "./Monitoring";
import MaskProofreading from "./MaskProofreading";
import Chatbot from "../components/Chatbot";
import { useWorkflow } from "../contexts/WorkflowContext";
import { logClientEvent } from "../logging/appEventLog";

const { Content } = Layout;

const MODULE_ITEMS = [
  { label: "Files", key: "files", icon: <FolderOpenOutlined /> },
  { label: "Visualize", key: "visualization", icon: <EyeOutlined /> },
  { label: "Train", key: "training", icon: <ExperimentOutlined /> },
  {
    label: "Infer",
    key: "inference",
    icon: <ThunderboltOutlined />,
  },
  { label: "Monitor", key: "monitoring", icon: <DashboardOutlined /> },
  {
    label: "Proofread",
    key: "mask-proofreading",
    icon: <BugOutlined />,
  },
];

function Views() {
  const [current, setCurrent] = useState("files");
  const [visitedTabs, setVisitedTabs] = useState(new Set(["files"]));
  const workflowContext = useWorkflow();
  const lastClientEffects = workflowContext?.lastClientEffects;
  const consumeClientEffects = workflowContext?.consumeClientEffects;
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [assistantContextOpen, setAssistantContextOpen] = useState(false);
  const [quickAgentRequest, setQuickAgentRequest] = useState(null);
  const [chatWidth, setChatWidth] = useState(460);
  const isResizing = useRef(false);
  const quickAgentRequestId = useRef(0);

  const [viewers, setViewers] = useState([]);
  const [isInferring, setIsInferring] = useState(false);

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

  useEffect(() => {
    if (!lastClientEffects) return;
    const target = lastClientEffects.navigate_to;
    if (target) {
      const targetKey = target === "model-training" ? "training" : target;
      setCurrent(targetKey);
      setVisitedTabs((prev) => new Set(prev).add(targetKey));
    }
    if (lastClientEffects.open_assistant) {
      setIsChatOpen(true);
    }
    if (lastClientEffects.show_workflow_context) {
      setAssistantContextOpen(true);
    }
    consumeClientEffects?.();
  }, [lastClientEffects, consumeClientEffects]);

  useEffect(() => {
    logClientEvent("view_changed", {
      level: "INFO",
      message: `Switched to ${current}`,
      source: "views",
      data: { view: current },
    });
  }, [current]);

  useEffect(() => {
    logClientEvent(isChatOpen ? "chat_opened" : "chat_closed", {
      level: "INFO",
      message: isChatOpen ? "Assistant drawer opened" : "Assistant drawer closed",
      source: "views",
      data: { width: chatWidth },
    });
  }, [chatWidth, isChatOpen]);

  const handleStartNewProject = async () => {
    const confirmed =
      typeof window === "undefined" ||
      window.confirm(
        "Start a new workflow? Existing workflow evidence stays saved, but this app session will start from setup.",
      );
    if (!confirmed) return;

    try {
      await workflowContext?.startNewWorkflow?.({
        metadata: { created_from: "new_project_button" },
      });
      setCurrent("files");
      setVisitedTabs(new Set(["files"]));
      message.success("Started a fresh workflow.");
    } catch (error) {
      console.error("Could not start a new workflow", error);
      message.error("Could not start a fresh workflow.");
    }
  };

  const handleAskWhatNext = () => {
    if (!workflowContext?.workflow?.id) {
      message.warning("Start or load a workflow first.");
      return;
    }
    quickAgentRequestId.current += 1;
    const request = {
      id: quickAgentRequestId.current,
      query: "What should I do next?",
      displayText: "What should I do next?",
      source: "quick_next",
    };
    setQuickAgentRequest(request);
    setIsChatOpen(true);
    logClientEvent("workflow_agent_quick_next_requested", {
      level: "INFO",
      source: "views",
      message: "Quick next-step assistant request",
      data: {
        workflowId: workflowContext.workflow.id,
        stage: workflowContext.workflow.stage,
        view: current,
      },
    });
  };

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

  if (workflowContext?.loading && !workflowContext?.workflow) {
    return (
      <Layout style={{ minHeight: "100vh", background: "#f6f7fb" }}>
        <Content
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#6b7280",
          }}
        >
          Loading workspace...
        </Content>
      </Layout>
    );
  }

  return (
    <Layout style={{ minHeight: "100vh", height: "100vh" }}>
      <div
        className="pytc-top-nav"
        style={{
          display: "flex",
          alignItems: "center",
          background: "#fff",
          paddingRight: 12,
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Menu
          onClick={onClick}
          selectedKeys={[current]}
          mode="horizontal"
          items={MODULE_ITEMS}
          className="pytc-top-menu"
          style={{
            lineHeight: "48px",
            paddingLeft: "12px",
            flex: 1,
            borderBottom: "none",
          }}
        />
        <Button
          onClick={handleAskWhatNext}
          title="Ask the assistant for the best next workflow step"
          disabled={!workflowContext?.workflow?.id}
        >
          What next?
        </Button>
        <Button onClick={handleStartNewProject} title="Start a fresh workflow">
          New project
        </Button>
        <Button
          type="primary"
          shape="circle"
          icon={<MessageOutlined />}
          onClick={() => setIsChatOpen(true)}
          style={{ marginLeft: 8 }}
        />
      </div>
      <Content
        style={{
          padding: "16px",
          flex: 1,
          minHeight: 0,
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
        {renderTabContent("mask-proofreading", <MaskProofreading />)}
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
            (e.currentTarget.style.backgroundColor =
              "var(--seg-accent-primary, #3f37c9)")
          }
          onMouseLeave={(e) =>
            !isResizing.current &&
            (e.currentTarget.style.backgroundColor = "transparent")
          }
        />
        <Chatbot
          onClose={() => setIsChatOpen(false)}
          forceShowWorkflowInspector={assistantContextOpen}
          onWorkflowInspectorConsumed={() => setAssistantContextOpen(false)}
          queuedWorkflowQuery={quickAgentRequest}
          onQueuedWorkflowQueryConsumed={(id) => {
            setQuickAgentRequest((currentRequest) =>
              currentRequest?.id === id ? null : currentRequest,
            );
          }}
        />
      </Drawer>
    </Layout>
  );
}

export default Views;
