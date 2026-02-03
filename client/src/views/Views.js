import React, { useState, useEffect } from "react";
import { Layout, Menu, message, Button, Drawer } from "antd";
import {
  FolderOpenOutlined,
  DesktopOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
  BugOutlined,
  ReadOutlined,
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
import apiClient from "../services/apiClient";
import { initTaskAgent } from "../utils/api";

const { Content } = Layout;

const PREF_FILE_NAME = "workflow_preference.json";
const PROJECT_CONTEXT =
  "Mitochondria segmentation on an electron microscopy volume.";

const TASK_CONTEXTS = {
  files: "File management for datasets and configuration files.",
  visualization: "Visualization of EM volumes and labels in Neuroglancer.",
  training: "Model training configuration and execution in PyTorch Connectomics.",
  inference: "Model inference configuration and execution in PyTorch Connectomics.",
  monitoring: "Tensorboard monitoring and training metrics.",
  synanno: "Synapse proofreading workflow.",
  "worm-error-handling": "Segmentation proofreading workflow.",
};

function Views() {
  // State
  const [current, setCurrent] = useState("files");
  const [visibleTabs, setVisibleTabs] = useState(new Set(["files"]));
  const [visitedTabs, setVisitedTabs] = useState(new Set(["files"]));
  const [workflowModalVisible, setWorkflowModalVisible] = useState(false);
  const [isManualChange, setIsManualChange] = useState(false); // Flag for "Change Startup Mode"
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [pendingChatPrompt, setPendingChatPrompt] = useState(null);
  const [apiReady, setApiReady] = useState(false);
  const [hasShownApiWarning, setHasShownApiWarning] = useState(false);

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

  const checkPreference = async (isMounted) => {
    try {
      const res = await apiClient.get('/files')
      const fileList = res.data || []

      // Find saved preference file
      const prefFile = fileList.find(f => f.name === PREF_FILE_NAME && !f.is_folder)

      if (prefFile && prefFile.physical_path) {
        try {
          let pathForUrl = prefFile.physical_path.replace(/\\/g, '/')
          if (pathForUrl.includes('uploads/')) {
            const parts = pathForUrl.split('uploads/')
            if (parts.length > 1) {
              pathForUrl = 'uploads/' + parts[parts.length - 1]
            }
          }
          const fileUrl = `${apiClient.defaults.baseURL || 'http://localhost:4242'}/${pathForUrl}`

          const contentRes = await fetch(fileUrl)
          if (contentRes.ok) {
            const data = await contentRes.json()
            if (data) {
              const modes = data.modes || data.mode
              if (modes) {
                applyModes(modes)
                return
              }
            }
          }
        } catch (err) {
          console.error('Error reading pref file content', err)
        }
      }

      // If no file found or error reading it, show selector (Initial Launch)
      if (isMounted) {
        setWorkflowModalVisible(true)
        setIsManualChange(false)
      }

    } catch (err) {
      if (isMounted) {
        setWorkflowModalVisible(true)
        setIsManualChange(false)
      }
    }
  }

  // Wait for API readiness before loading preferences
  useEffect(() => {
    let isMounted = true;
    let pollId;

    const pollApi = async () => {
      try {
        await apiClient.get("/health");
        if (!isMounted) return;
        setApiReady(true);
        checkPreference(isMounted);
        if (pollId) clearInterval(pollId);
      } catch (err) {
        if (!isMounted) return;
        setApiReady(false);
        if (!hasShownApiWarning) {
          setHasShownApiWarning(true);
          message.warning("API server is not ready yet. Retrying...");
        }
      }
    };

    pollApi();
    pollId = setInterval(pollApi, 2000);

    return () => {
      isMounted = false;
      if (pollId) clearInterval(pollId);
    };
  }, [hasShownApiWarning]);

  const handleWorkflowSelect = async (modes, remember) => {
    setWorkflowModalVisible(false);

    // Render logic: Only if NOT manual change
    if (!isManualChange) {
      applyModes(modes);
    }

    // Persistence Logic
    try {
      if (!apiReady) {
        message.warning('API server is not ready. Preference was not saved.')
        setIsManualChange(false)
        return
      }
      // 1. Always delete existing to avoid staleness or duplicates
      const res = await apiClient.get("/files");
      const existing = (res.data || []).filter(
        (f) => f.name === PREF_FILE_NAME,
      );
      for (const f of existing) {
        await apiClient.delete(`/files/${f.id}`);
      }

      // 2. If Remember is checked, Save new
      if (remember) {
        const jsonContent = JSON.stringify({ modes });
        const blob = new Blob([jsonContent], { type: "application/json" });
        const file = new File([blob], PREF_FILE_NAME, {
          type: "application/json",
        });

        const formData = new FormData();
        formData.append("file", file);
        formData.append("path", "root");

        await apiClient.post("/files/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        if (isManualChange) {
          message.success("Preferences saved for next launch");
        }
      } else {
        // Remember is UNCHECKED
        if (isManualChange) {
          message.info("Startup preference cleared");
        }
      }
    } catch (err) {
      console.error("Failed to update preference", err);
      message.error("Failed to update preference");
    }

    // Reset manual flag
    setIsManualChange(false);

    // Initialize task-scoped agents for selected modules
    try {
      const modeList = Array.isArray(modes) ? modes : [modes];
      await Promise.all(
        modeList.map((mode) =>
          initTaskAgent(
            mode,
            PROJECT_CONTEXT,
            TASK_CONTEXTS[mode] || "Module assistance.",
          ),
        ),
      );
    } catch (err) {
      console.warn("Failed to initialize task agents:", err);
    }
  };

  // IPC Listener
  useEffect(() => {
    let ipcRenderer;
    try {
      ipcRenderer = window.require("electron").ipcRenderer;
    } catch (e) {
      return;
    }

    const handleToggleTab = (event, key, checked) => {
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

    const handleResetPreference = () => {
      // User clicked "Change Startup Mode"
      // We set isManualChange = true, so selecting doesn't render immediately
      setIsManualChange(true);
      setWorkflowModalVisible(true);
    };

    ipcRenderer.on("toggle-tab", handleToggleTab);
    ipcRenderer.on("reset-preference", handleResetPreference);

    return () => {
      ipcRenderer.removeListener("toggle-tab", handleToggleTab);
      ipcRenderer.removeListener("reset-preference", handleResetPreference);
    };
  }, [current]);

  useEffect(() => {
    const handleChatPrompt = (event) => {
      const prompt = event.detail?.prompt;
      if (!prompt) return;
      setPendingChatPrompt(prompt);
      setIsChatOpen(true);
    };
    window.addEventListener("chatbot:prompt", handleChatPrompt);
    return () => {
      window.removeEventListener("chatbot:prompt", handleChatPrompt);
    };
  }, []);

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
          setIsManualChange(false);
          // If initial launch and cancelled, maybe just files?
          if (!isManualChange && visitedTabs.size <= 1) {
            // simple heuristic
            // already files by default
          }
        }}
        isManual={isManualChange}
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
        width={380}
        mask={false}
        closable={false}
        destroyOnClose
        styles={{ header: { display: 'none' }, body: { padding: 0 } }}
      >
        <Chatbot
          onClose={() => setIsChatOpen(false)}
          pendingPrompt={pendingChatPrompt}
          onPromptConsumed={() => setPendingChatPrompt(null)}
        />
      </Drawer>
    </Layout>
  );
}

export default Views;
