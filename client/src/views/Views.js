import React, { useState, useEffect, useRef, useCallback } from "react";
import { Layout, Menu, Button, Drawer, message } from "antd";
import {
  FolderOpenOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  BugOutlined,
  MessageOutlined,
  ProjectOutlined,
} from "@ant-design/icons";
import FilesManager from "./FilesManager";
import Visualization from "./Visualization";
import ModelTraining from "./ModelTraining";
import ModelInference from "./ModelInference";
import MaskProofreading from "./MaskProofreading";
import ProjectManager from "./project-manager/ProjectManager";
import ProjectProgress from "./ProjectProgress";
import Chatbot from "../components/Chatbot";
import { useWorkflow } from "../contexts/WorkflowContext";
import { logClientEvent } from "../logging/appEventLog";

const { Content } = Layout;

const MODULE_ITEMS = [
  { label: "Files", key: "files", icon: <FolderOpenOutlined /> },
  { label: "Visualize", key: "visualization", icon: <EyeOutlined /> },
  { label: "Train Model", key: "training", icon: <ExperimentOutlined /> },
  {
    label: "Run Model",
    key: "inference",
    icon: <ThunderboltOutlined />,
  },
  {
    label: "Workflow",
    key: "project-progress",
    icon: <ProjectOutlined />,
  },
  {
    label: "Proofread",
    key: "mask-proofreading",
    icon: <BugOutlined />,
  },
  {
    label: "Project Manager",
    key: "project-manager",
    icon: <ProjectOutlined />,
  },
];

const formatCount = (value, label) => `${Number(value || 0)} ${label}`;

const workflowPhaseTone = {
  setup: "#6b7280",
  inspect: "#2563eb",
  proofread: "#b45309",
  train: "#4338ca",
  infer: "#047857",
  evaluate: "#7c3aed",
};

function WorkflowOverviewStrip({ overview, workflow, onNavigate }) {
  const summary = overview?.volume_summary || {};
  const phase = overview?.phase || workflow?.stage || "setup";
  const phaseLabel =
    overview?.phase_label || String(phase || "Setup").replace(/_/g, " ");
  const projectName =
    overview?.project_name || workflow?.title || "Segmentation workflow";
  const blocker = overview?.blockers?.[0] || null;
  const activeRun = overview?.active_runs?.[0] || null;
  const action = overview?.recommended_next_actions?.[0] || null;
  const tone = workflowPhaseTone[phase] || "#4338ca";
  const counts = [
    formatCount(summary.ground_truth, "GT"),
    formatCount(summary.needs_proofreading, "draft"),
    formatCount(summary.missing_segmentation, "missing"),
  ];

  return (
    <div
      aria-label="Workflow overview"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 14px",
        borderBottom: "1px solid #eceef3",
        background: "#fbfbfd",
        minHeight: 42,
        overflowX: "auto",
        whiteSpace: "nowrap",
      }}
    >
      <button
        type="button"
        onClick={() => onNavigate("project-progress")}
        style={{
          border: "none",
          background: "transparent",
          padding: 0,
          color: "#111827",
          fontWeight: 650,
          cursor: "pointer",
        }}
      >
        {projectName}
      </button>
      <span
        style={{
          color: tone,
          border: `1px solid ${tone}`,
          borderRadius: 999,
          padding: "2px 9px",
          fontSize: 12,
          fontWeight: 650,
          textTransform: "capitalize",
        }}
      >
        {phaseLabel}
      </span>
      <button
        type="button"
        onClick={() => onNavigate("project-progress")}
        style={{
          border: "none",
          background: "transparent",
          color: "#4b5563",
          cursor: "pointer",
          padding: 0,
        }}
      >
        {counts.join(" · ")}
      </button>
      {activeRun ? (
        <span style={{ color: "#4338ca", fontWeight: 600 }}>
          {activeRun.run_type} {activeRun.status}
        </span>
      ) : blocker ? (
        <button
          type="button"
          onClick={() => onNavigate(blocker.target_view || "project-progress")}
          style={{
            border: "none",
            background: "transparent",
            color: blocker.severity === "blocking" ? "#b91c1c" : "#92400e",
            cursor: "pointer",
            padding: 0,
          }}
          title={blocker.detail}
        >
          {blocker.label}
        </button>
      ) : (
        <span style={{ color: "#047857", fontWeight: 600 }}>No blockers</span>
      )}
      {action && (
        <Button
          size="small"
          onClick={() => onNavigate(action.target_view)}
          style={{ marginLeft: "auto" }}
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}

function Views() {
  const [current, setCurrent] = useState("files");
  const [visitedTabs, setVisitedTabs] = useState(new Set(["files"]));
  const workflowContext = useWorkflow();
  const lastClientEffects = workflowContext?.lastClientEffects;
  const consumeClientEffects = workflowContext?.consumeClientEffects;
  const refreshProjectProgress = workflowContext?.refreshProjectProgress;
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [quickAgentRequest, setQuickAgentRequest] = useState(null);
  const [chatWidth, setChatWidth] = useState(460);
  const isResizing = useRef(false);
  const quickAgentRequestId = useRef(0);

  const [viewers, setViewers] = useState([]);
  const [isInferring, setIsInferring] = useState(false);

  /*
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
*/

  const onClick = (e) => {
    setCurrent(e.key);
    setVisitedTabs((prev) => new Set(prev).add(e.key));
  };

  const navigateTo = useCallback((key) => {
    if (!key) return;
    const targetKey = key === "monitoring" || key === "model-training" ? "training" : key;
    setCurrent(targetKey);
    setVisitedTabs((prev) => new Set(prev).add(targetKey));
  }, []);

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
      navigateTo(target);
    }
    if (lastClientEffects.open_assistant) {
      setIsChatOpen(true);
    }
    if (lastClientEffects.show_workflow_context) {
      navigateTo("project-progress");
    }
    if (lastClientEffects.refresh_project_progress) {
      refreshProjectProgress?.();
    }
    consumeClientEffects?.();
  }, [lastClientEffects, consumeClientEffects, refreshProjectProgress, navigateTo]);

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
      <WorkflowOverviewStrip
        overview={workflowContext?.workflowOverview}
        workflow={workflowContext?.workflow}
        onNavigate={navigateTo}
      />
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
        {renderTabContent("project-progress", <ProjectProgress />)}
        {renderTabContent(
          "inference",
          <ModelInference
            isInferring={isInferring}
            setIsInferring={setIsInferring}
          />,
        )}
        {renderTabContent("mask-proofreading", <MaskProofreading />)}
        {/* {renderTabContent("synanno", <ProofReading />)} */}
        {/* {renderTabContent("worm-error-handling", <WormErrorHandling />)} */}
        {renderTabContent("project-manager", <ProjectManager />)}
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
