import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Layout,
  message,
  Space,
  Typography,
  Button,
  Popover,
  Slider,
  Card,
} from "antd";
import { SettingOutlined } from "@ant-design/icons";
import DatasetLoader from "./DatasetLoader";
import ProgressTracker from "./ProgressTracker";
import InstanceNavigator from "./InstanceNavigator";
import InstanceViewport from "./InstanceViewport";
import ProofreadingEditor from "./ProofreadingEditor";
import { apiClient } from "../../api";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

function DetectionWorkflow({ sessionId, setSessionId, refreshTrigger }) {
  const [projectName, setProjectName] = useState("");
  const [totalLayers, setTotalLayers] = useState(0);
  const [instances, setInstances] = useState([]);
  const [instanceMode, setInstanceMode] = useState("none");
  const [activeInstanceId, setActiveInstanceId] = useState(null);
  const [activeInstance, setActiveInstance] = useState(null);
  const [filterText, setFilterText] = useState("");
  const [loadingInstances, setLoadingInstances] = useState(false);
  const [loadingView, setLoadingView] = useState(false);
  const [viewState, setViewState] = useState({
    imageBase64: null,
    maskAllBase64: null,
    maskActiveBase64: null,
    maskRawBase64: null,
    zIndex: 0,
  });
  const [overlayAllAlpha, setOverlayAllAlpha] = useState(0.08);
  const [overlayActiveAlpha, setOverlayActiveAlpha] = useState(0.8);
  const [showEditor, setShowEditor] = useState(false);
  const [savingMask, setSavingMask] = useState(false);
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1440,
  );

  const requestRef = useRef(0);

  useEffect(() => {
    if (sessionId) {
      loadInstances();
    }
  }, [sessionId, refreshTrigger]);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!sessionId || !activeInstanceId) return;
    loadInstanceView(activeInstanceId, viewState.zIndex);
  }, [sessionId, activeInstanceId, viewState.zIndex]);

  useEffect(() => {
    const handleKeyPress = (e) => {
      const target = e.target;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      )
        return;

      if (!sessionId || !activeInstanceId) return;

      switch (e.key.toLowerCase()) {
        case "c":
          handleInstanceClassify("correct");
          break;
        case "x":
          handleInstanceClassify("incorrect");
          break;
        case "u":
          handleInstanceClassify("unsure");
          break;
        case "arrowright":
          goToNextInstance();
          break;
        case "arrowleft":
          goToPreviousInstance();
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [sessionId, activeInstanceId, instances]);

  const stats = useMemo(() => {
    const total = instances.length;
    const correct = instances.filter((i) => i.classification === "correct").length;
    const incorrect = instances.filter((i) => i.classification === "incorrect").length;
    const unsure = instances.filter((i) => i.classification === "unsure").length;
    const error = instances.filter((i) => i.classification === "error").length;
    const reviewed = total - error;
    const progress_percent = total > 0 ? (reviewed / total) * 100 : 0;

    return {
      correct,
      incorrect,
      unsure,
      error,
      total,
      reviewed,
      progress_percent: Math.round(progress_percent * 100) / 100,
    };
  }, [instances]);

  const handleDatasetLoad = async (datasetPath, maskPath, projectName) => {
    setLoadingInstances(true);
    try {
      const response = await apiClient.post("/eh/detection/load", {
        dataset_path: datasetPath,
        mask_path: maskPath || null,
        project_name: projectName,
      });

      setSessionId(response.data.session_id);
      setProjectName(response.data.project_name);
      setTotalLayers(response.data.total_layers);
      message.success(
        `Loaded ${response.data.total_layers} slices successfully`,
      );
      await loadInstances(response.data.session_id, true);
    } catch (error) {
      console.error("Failed to load dataset:", error);
      message.error(error.response?.data?.detail || "Failed to load dataset");
    } finally {
      setLoadingInstances(false);
    }
  };

  const loadInstances = async (overrideSessionId, forceView = false) => {
    const sessionToUse = overrideSessionId ?? sessionId;
    if (!sessionToUse) return;
    setLoadingInstances(true);
    try {
      const response = await apiClient.get("/eh/detection/instances", {
        params: { session_id: sessionToUse },
      });

      const instanceList = response.data.instances || [];
      setInstances(instanceList);
      setInstanceMode(response.data.instance_mode || "none");
      setTotalLayers(response.data.total_layers || 0);

      const firstUnreviewed = instanceList.find(
        (inst) => inst.classification === "error",
      );
      const initialInstance = firstUnreviewed || instanceList[0];
      if (initialInstance) {
        setActiveInstanceId(initialInstance.id);
        setActiveInstance(initialInstance);
        setViewState((prev) => ({
          ...prev,
          zIndex: initialInstance.com_z,
        }));
        if (forceView) {
          await loadInstanceView(
            initialInstance.id,
            initialInstance.com_z,
            sessionToUse,
          );
        }
      }
    } catch (error) {
      console.error("Failed to load instances:", error);
      message.error("Failed to load instances");
    } finally {
      setLoadingInstances(false);
    }
  };

  const loadInstanceView = async (instanceId, zIndex, overrideSessionId) => {
    const sessionToUse = overrideSessionId ?? sessionId;
    if (!sessionToUse) return;
    const requestId = ++requestRef.current;
    setLoadingView(true);
    try {
      const response = await apiClient.get("/eh/detection/instance-view", {
        params: {
          session_id: sessionToUse,
          instance_id: instanceId,
          z_index: zIndex,
        },
      });

      if (requestId !== requestRef.current) return;

      setViewState({
        imageBase64: response.data.image_base64,
        maskAllBase64: response.data.mask_all_base64,
        maskActiveBase64: response.data.mask_active_base64,
        maskRawBase64: response.data.mask_raw_base64,
        zIndex: response.data.z_index,
      });
    } catch (error) {
      console.error("Failed to load instance view:", error);
      message.error("Failed to load instance view");
    } finally {
      if (requestId === requestRef.current) {
        setLoadingView(false);
      }
    }
  };

  const selectInstance = (instance) => {
    setActiveInstanceId(instance.id);
    setActiveInstance(instance);
    setViewState((prev) => ({ ...prev, zIndex: instance.com_z }));
  };

  const goToNextInstance = () => {
    if (!activeInstanceId || instances.length === 0) return;
    const index = instances.findIndex((inst) => inst.id === activeInstanceId);
    const next = instances[index + 1] || instances[0];
    if (next) selectInstance(next);
  };

  const goToPreviousInstance = () => {
    if (!activeInstanceId || instances.length === 0) return;
    const index = instances.findIndex((inst) => inst.id === activeInstanceId);
    const prev = instances[index - 1] || instances[instances.length - 1];
    if (prev) selectInstance(prev);
  };

  const handleInstanceClassify = async (classification) => {
    if (!activeInstanceId) return;
    try {
      await apiClient.post("/eh/detection/instance-classify", {
        session_id: sessionId,
        instance_ids: [activeInstanceId],
        classification,
      });

      setInstances((prev) =>
        prev.map((inst) =>
          inst.id === activeInstanceId
            ? { ...inst, classification }
            : inst,
        ),
      );

      if (activeInstance && activeInstance.id === activeInstanceId) {
        setActiveInstance({ ...activeInstance, classification });
      }

      message.success(`Instance ${activeInstanceId} marked ${classification}`);
    } catch (error) {
      console.error("Failed to classify instance:", error);
      message.error("Failed to classify instance");
    }
  };

  const handleSliceChange = (value) => {
    setViewState((prev) => ({ ...prev, zIndex: value }));
  };

  const handleOpenEditor = () => {
    if (!activeInstanceId) return;
    setShowEditor((prev) => !prev);
  };

  const handleSaveMask = async (maskBase64) => {
    if (!sessionId) return;
    setSavingMask(true);
    try {
      await apiClient.post("/eh/detection/mask", {
        session_id: sessionId,
        layer_index: viewState.zIndex,
        mask_base64: maskBase64,
      });
      message.success("Mask updated");
      loadInstanceView(activeInstanceId, viewState.zIndex);
    } catch (error) {
      console.error("Failed to save mask:", error);
      message.error(error.response?.data?.detail || "Failed to save mask");
    } finally {
      setSavingMask(false);
    }
  };

  if (!sessionId) {
    return (
      <div style={{ padding: "24px 0" }}>
        <DatasetLoader onLoad={handleDatasetLoad} loading={loadingInstances} />
      </div>
    );
  }

  return (
    <Layout
      style={{
        minHeight: "calc(100vh - 210px)",
        background: "transparent",
      }}
    >
      <Content style={{ padding: 0 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 8,
          }}
        >
          <Title level={5} style={{ margin: 0 }}>
            Instance proofreading
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Instances are the unit of review
          </Text>
        </div>

        <Layout style={{ background: "transparent" }}>
          <Content style={{ padding: "0 14px 0 0" }}>
            {loadingInstances && instances.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center" }}>
                <Title level={4}>Preparing instances…</Title>
                <Text type="secondary">
                  Building the instance list and loading the first view.
                </Text>
              </div>
            ) : instanceMode === "none" ? (
              <div style={{ padding: 32, textAlign: "center" }}>
                <Title level={4}>Mask required</Title>
                <Text type="secondary">
                  Load a dataset with a mask to enable instance proofreading.
                </Text>
              </div>
            ) : (
              <>
                <InstanceViewport
                  imageBase64={viewState.imageBase64}
                  maskAllBase64={viewState.maskAllBase64}
                  maskActiveBase64={viewState.maskActiveBase64}
                  loading={loadingView || loadingInstances}
                  zIndex={viewState.zIndex}
                  totalLayers={totalLayers}
                  overlayAllAlpha={overlayAllAlpha}
                  overlayActiveAlpha={overlayActiveAlpha}
                  onPrevSlice={() =>
                    handleSliceChange(Math.max(viewState.zIndex - 1, 0))
                  }
                  onNextSlice={() =>
                    handleSliceChange(
                      Math.min(viewState.zIndex + 1, totalLayers - 1),
                    )
                  }
                  onSliceChange={handleSliceChange}
                  onOpenEditor={handleOpenEditor}
                />

                <div
                  style={{
                    marginTop: showEditor ? 16 : 0,
                    maxHeight: showEditor ? "720px" : "0px",
                    opacity: showEditor ? 1 : 0,
                    overflow: "hidden",
                    transition: "all 220ms ease",
                    pointerEvents: showEditor ? "auto" : "none",
                  }}
                >
                  <Card
                    bodyStyle={{ height: "640px", padding: 16 }}
                    title={`Mask editor · Slice ${viewState.zIndex + 1}`}
                    extra={
                      <Button onClick={() => setShowEditor(false)}>
                        Close editor
                      </Button>
                    }
                  >
                    <ProofreadingEditor
                      imageBase64={viewState.imageBase64}
                      maskBase64={viewState.maskRawBase64}
                      onSave={handleSaveMask}
                      onNext={() =>
                        handleSliceChange(
                          Math.min(viewState.zIndex + 1, totalLayers - 1),
                        )
                      }
                      onPrevious={() =>
                        handleSliceChange(Math.max(viewState.zIndex - 1, 0))
                      }
                      currentLayer={viewState.zIndex}
                      totalLayers={totalLayers}
                      layerName={`Slice ${viewState.zIndex + 1}`}
                    />
                    {savingMask && (
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary">Saving mask…</Text>
                      </div>
                    )}
                  </Card>
                </div>
              </>
            )}
          </Content>

          <Sider
            width={Math.max(260, Math.min(320, windowWidth * 0.26))}
            theme="light"
            style={{
              borderLeft: "1px solid #eef2f7",
              background: "transparent",
            }}
          >
            <div style={{ padding: "12px 12px", display: "grid", gap: 12 }}>
              {activeInstance && instanceMode !== "none" && (
                <Card
                  size="small"
                  bordered={false}
                  style={{ background: "#fff" }}
                >
                  <Text style={{ fontSize: 12 }} type="secondary">
                    Active instance
                  </Text>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    #{activeInstance.id}
                  </div>
                  <Space size="small" style={{ marginTop: 8 }}>
                    <Button
                      size="small"
                      type="primary"
                      onClick={() => handleInstanceClassify("correct")}
                    >
                      Looks good
                    </Button>
                    <Button
                      size="small"
                      danger
                      onClick={() => handleInstanceClassify("incorrect")}
                    >
                      Needs fix
                    </Button>
                    <Button
                      size="small"
                      style={{ background: "#f59e0b", color: "#fff" }}
                      onClick={() => handleInstanceClassify("unsure")}
                    >
                      Unsure
                    </Button>
                  </Space>
                </Card>
              )}

              <Card size="small" bordered={false} style={{ background: "#fff" }}>
                <Text style={{ fontSize: 12 }} type="secondary">
                  View
                </Text>
                <div style={{ marginTop: 8 }}>
                  <Text style={{ fontSize: 12 }}>All instances</Text>
                  <Slider
                    min={0}
                    max={100}
                    value={Math.round(overlayAllAlpha * 100)}
                    onChange={(value) => setOverlayAllAlpha(value / 100)}
                  />
                  <Text style={{ fontSize: 12 }}>Active instance</Text>
                  <Slider
                    min={0}
                    max={100}
                    value={Math.round(overlayActiveAlpha * 100)}
                    onChange={(value) => setOverlayActiveAlpha(value / 100)}
                  />
                </div>
              </Card>

              <ProgressTracker
                stats={stats}
                projectName={projectName}
                totalLayers={instances.length}
                unitLabel="instances"
                onNewSession={() => {
                  setSessionId(null);
                  setActiveInstanceId(null);
                  setInstances([]);
                }}
                onJumpToNext={goToNextInstance}
              />

              <InstanceNavigator
                instances={instances}
                activeInstanceId={activeInstanceId}
                onSelect={selectInstance}
                onPrev={goToPreviousInstance}
                onNext={goToNextInstance}
                filterText={filterText}
                onFilterText={setFilterText}
                instanceMode={instanceMode}
              />
            </div>
          </Sider>
        </Layout>
      </Content>

      {/* Editor is now inline to keep context */}
    </Layout>
  );
}

export default DetectionWorkflow;
