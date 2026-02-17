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
  Drawer,
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
  const [viewAxis, setViewAxis] = useState("xy");
  const [axisTotal, setAxisTotal] = useState(0);
  const [viewState, setViewState] = useState({
    imageBase64: null,
    maskAllBase64: null,
    maskActiveBase64: null,
    maskRawBase64: null,
    zIndex: 0,
    axis: "xy",
    total: 0,
  });
  const [sliderZ, setSliderZ] = useState(0);
  const [overlayAllAlpha, setOverlayAllAlpha] = useState(0.08);
  const [overlayActiveAlpha, setOverlayActiveAlpha] = useState(0.8);
  const [showEditor, setShowEditor] = useState(false);
  const [savingMask, setSavingMask] = useState(false);
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1440,
  );
  const [showInstanceBrowser, setShowInstanceBrowser] = useState(false);

  const requestRef = useRef(0);
  const viewCache = useRef(new Map());
  const viewCacheOrder = useRef([]);
  const previewUrlsRef = useRef([]);
  const viewCacheLimit = 50;

  const axisOptions = useMemo(
    () => [
      { label: "XY", value: "xy" },
      { label: "ZX", value: "zx" },
      { label: "ZY", value: "zy" },
    ],
    [],
  );

  const getAxisIndexForInstance = (instance, axis) => {
    if (!instance) return 0;
    if (axis === "zx") return instance.com_y ?? 0;
    if (axis === "zy") return instance.com_x ?? 0;
    return instance.com_z ?? 0;
  };

  useEffect(() => {
    if (sessionId) {
      loadInstances();
    }
  }, [sessionId, refreshTrigger]);

  useEffect(() => {
    const storedAll = Number(localStorage.getItem("mask-proofreading-overlay-all"));
    const storedActive = Number(
      localStorage.getItem("mask-proofreading-overlay-active"),
    );
    const storedAxis = localStorage.getItem("mask-proofreading-axis");
    if (!Number.isNaN(storedAll) && storedAll > 0) {
      setOverlayAllAlpha(Math.min(Math.max(storedAll, 0.01), 1));
    }
    if (!Number.isNaN(storedActive) && storedActive > 0) {
      setOverlayActiveAlpha(Math.min(Math.max(storedActive, 0.01), 1));
    }
    if (storedAxis && ["xy", "zx", "zy"].includes(storedAxis)) {
      setViewAxis(storedAxis);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(
      "mask-proofreading-overlay-all",
      overlayAllAlpha.toString(),
    );
  }, [overlayAllAlpha]);

  useEffect(() => {
    localStorage.setItem(
      "mask-proofreading-overlay-active",
      overlayActiveAlpha.toString(),
    );
  }, [overlayActiveAlpha]);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!sessionId || !activeInstanceId) return;
    loadInstanceView(activeInstanceId, viewState.zIndex, showEditor, undefined, viewAxis);
  }, [sessionId, activeInstanceId, viewState.zIndex, showEditor, viewAxis]);

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
        case "1":
          handleAxisChange("xy");
          break;
        case "2":
          handleAxisChange("zx");
          break;
        case "3":
          handleAxisChange("zy");
          break;
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
    viewCache.current.forEach((cached) => {
      [cached.imageBase64, cached.maskAllBase64, cached.maskActiveBase64, cached.maskRawBase64]
        .filter((url) => url && url.startsWith("blob:"))
        .forEach((url) => URL.revokeObjectURL(url));
    });
    viewCache.current.clear();
    viewCacheOrder.current = [];
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrlsRef.current = [];
    try {
      const response = await apiClient.get("/eh/detection/instances", {
        params: { session_id: sessionToUse },
      });

      const instanceList = response.data.instances || [];
      setInstances(instanceList);
      setInstanceMode(response.data.instance_mode || "none");
      setTotalLayers(response.data.total_layers || 0);
      setViewAxis("xy");
      setAxisTotal(response.data.total_layers || 0);

      const firstUnreviewed = instanceList.find(
        (inst) => inst.classification === "error",
      );
      const initialInstance = firstUnreviewed || instanceList[0];
      if (initialInstance) {
        const axisIndex = getAxisIndexForInstance(initialInstance, "xy");
        setActiveInstanceId(initialInstance.id);
        setActiveInstance(initialInstance);
        setViewState((prev) => ({
          ...prev,
          zIndex: axisIndex,
          axis: "xy",
        }));
        if (forceView) {
          await loadInstanceView(
            initialInstance.id,
            axisIndex,
            false,
            sessionToUse,
            "xy",
            response.data.instance_mode || "none",
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

  const loadInstanceView = async (
    instanceId,
    zIndex,
    includeRaw,
    overrideSessionId,
    axisOverride,
    modeOverride,
  ) => {
    const sessionToUse = overrideSessionId ?? sessionId;
    if (!sessionToUse) return;
    const axisToUse = axisOverride ?? viewAxis;
    const includeAll = (modeOverride ?? instanceMode) === "instance";
    const cacheKey = `${instanceId}:${axisToUse}:${zIndex}`;
    const cached = viewCache.current.get(cacheKey);
    if (cached && (!includeRaw || cached.maskRawBase64)) {
      setViewState({
        imageBase64: cached.imageBase64,
        maskAllBase64: cached.maskAllBase64,
        maskActiveBase64: cached.maskActiveBase64,
        maskRawBase64: cached.maskRawBase64,
        zIndex: cached.zIndex,
        axis: cached.axis,
        total: cached.total,
      });
      setAxisTotal(cached.total ?? axisTotal);
      setSliderZ(cached.zIndex);
      return;
    }
    if (cached && includeRaw && !cached.maskRawBase64 && axisToUse === "xy") {
      try {
        const rawPayload = await fetchInstanceBundle({
          sessionId: sessionToUse,
          instanceId,
          axis: axisToUse,
          zIndex: cached.zIndex,
          kinds: ["mask_raw"],
          maxDim: null,
        });
        const merged = { ...cached, maskRawBase64: rawPayload.maskRawBase64 };
        cacheView(cacheKey, merged);
        setViewState(merged);
        setAxisTotal(merged.total);
        return;
      } catch (error) {
        // fallback to full load
      }
    }
    const requestId = ++requestRef.current;
    setLoadingView(true);
    try {
      const previewKinds = ["image", "mask_active"];
      const fullKinds = ["image", "mask_active"];
      if (includeAll) {
        previewKinds.push("mask_all");
        fullKinds.push("mask_all");
      }
      const previewPayload = await fetchInstanceBundle({
        sessionId: sessionToUse,
        instanceId,
        axis: axisToUse,
        zIndex,
        kinds: previewKinds,
        maxDim: 512,
      });

      if (requestId !== requestRef.current) return;
      setPreviewView(previewPayload);
      setSliderZ(previewPayload.zIndex);
      setLoadingView(false);

      const fullPayload = await fetchInstanceBundle({
        sessionId: sessionToUse,
        instanceId,
        axis: axisToUse,
        zIndex: previewPayload.zIndex,
        kinds: fullKinds,
        maxDim: null,
      });

      if (requestId !== requestRef.current) return;

      if (includeRaw && axisToUse === "xy") {
        const rawPayload = await fetchInstanceBundle({
          sessionId: sessionToUse,
          instanceId,
          axis: axisToUse,
          zIndex: fullPayload.zIndex,
          kinds: ["mask_raw"],
          maxDim: null,
        });
        fullPayload.maskRawBase64 = rawPayload.maskRawBase64;
      }

      previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      previewUrlsRef.current = [];

      cacheView(cacheKey, fullPayload);
      setViewState(fullPayload);
      setAxisTotal(fullPayload.total);
      setSliderZ(fullPayload.zIndex);

      prefetchAdjacent(
        instanceId,
        fullPayload.zIndex,
        sessionToUse,
        axisToUse,
        fullPayload.total,
      );
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
    const axisIndex = getAxisIndexForInstance(instance, viewAxis);
    setActiveInstanceId(instance.id);
    setActiveInstance(instance);
    setViewState((prev) => ({ ...prev, zIndex: axisIndex }));
    setSliderZ(axisIndex);
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
    const maxIndex = Math.max((axisTotal || totalLayers) - 1, 0);
    const nextIndex = Math.max(0, Math.min(value, maxIndex));
    setSliderZ(nextIndex);
  };

  const handleSliceCommit = (value) => {
    if (!activeInstanceId) return;
    const maxIndex = Math.max((axisTotal || totalLayers) - 1, 0);
    const nextIndex = Math.max(0, Math.min(value, maxIndex));
    setSliderZ(nextIndex);
    loadInstanceView(activeInstanceId, nextIndex, false, undefined, viewAxis);
  };

  const handleOpenEditor = () => {
    if (!activeInstanceId) return;
    const axisIndex =
      viewAxis !== "xy"
        ? getAxisIndexForInstance(activeInstance, "xy")
        : viewState.zIndex;
    if (viewAxis !== "xy") {
      setViewAxis("xy");
      setViewState((prev) => ({ ...prev, zIndex: axisIndex }));
    }
    setShowEditor((prev) => {
      const next = !prev;
      if (next) {
        loadInstanceView(activeInstanceId, axisIndex, true, undefined, "xy");
      }
      return next;
    });
  };

  const prefetchAdjacent = async (
    instanceId,
    zIndex,
    sessionToUse,
    axisToUse,
    axisTotalValue,
  ) => {
    const totalForAxis = axisTotalValue || axisTotal || totalLayers;
    if (!sessionToUse || !totalForAxis) return;
    const neighbors = [
      Math.max(zIndex - 2, 0),
      Math.max(zIndex - 1, 0),
      Math.min(zIndex + 1, totalForAxis - 1),
      Math.min(zIndex + 2, totalForAxis - 1),
    ];
    const includeAll = instanceMode === "instance";
    const kinds = ["image", "mask_active"];
    if (includeAll) kinds.push("mask_all");
    for (const neighbor of neighbors) {
      const key = `${instanceId}:${axisToUse}:${neighbor}`;
      if (viewCache.current.has(key)) continue;
      try {
        const payload = await fetchInstanceBundle({
          sessionId: sessionToUse,
          instanceId,
          axis: axisToUse,
          zIndex: neighbor,
          kinds,
          maxDim: null,
        });
        cacheView(key, payload);
      } catch (error) {
        // Prefetch failure is non-fatal
      }
    }
  };

  const setPreviewView = (payload) => {
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrlsRef.current = [
      payload.imageBase64,
      payload.maskAllBase64,
      payload.maskActiveBase64,
    ].filter((url) => url && url.startsWith("blob:"));
    setViewState(payload);
    setAxisTotal(payload.total);
  };

  const cacheView = (key, payload) => {
    viewCache.current.set(key, payload);
    viewCacheOrder.current.push(key);
    if (viewCacheOrder.current.length > viewCacheLimit) {
      const oldest = viewCacheOrder.current.shift();
      const cached = viewCache.current.get(oldest);
      if (cached) {
        [cached.imageBase64, cached.maskAllBase64, cached.maskActiveBase64, cached.maskRawBase64]
          .filter((url) => url && url.startsWith("blob:"))
          .forEach((url) => URL.revokeObjectURL(url));
      }
      viewCache.current.delete(oldest);
    }
  };

  const fetchInstanceBundle = async ({
    sessionId,
    instanceId,
    axis,
    zIndex,
    kinds,
    maxDim,
  }) => {
    const wantsActive = kinds.includes("mask_active");
    const imageKinds = kinds.filter((kind) => kind !== "mask_active");

    const requests = imageKinds.map((kind) =>
      apiClient.get("/eh/detection/instance-image", {
        params: {
          session_id: sessionId,
          instance_id: instanceId,
          axis,
          z_index: zIndex,
          kind,
          max_dim: maxDim || undefined,
        },
        responseType: "blob",
      }),
    );

    const [responses, sparseActive] = await Promise.all([
      requests.length ? Promise.all(requests) : Promise.resolve([]),
      wantsActive
        ? fetchSparseActiveMask({
            sessionId,
            instanceId,
            axis,
            zIndex,
          })
        : Promise.resolve(null),
    ]);

    const metaResponse = responses[0];
    const resolvedIndex = Number(
      metaResponse?.headers?.["x-z-index"] ??
        sparseActive?.z_index ??
        zIndex ??
        0,
    );
    const total = Number(
      metaResponse?.headers?.["x-total-layers"] ??
        sparseActive?.total_layers ??
        totalLayers ??
        0,
    );
    const resolvedAxis = metaResponse?.headers?.["x-axis"] ?? sparseActive?.axis ?? axis;

    const urls = {};
    responses.forEach((response, idx) => {
      const kind = imageKinds[idx];
      const url = URL.createObjectURL(response.data);
      if (kind === "image") urls.imageBase64 = url;
      if (kind === "mask_all") urls.maskAllBase64 = url;
      if (kind === "mask_raw") urls.maskRawBase64 = url;
    });

    if (sparseActive) {
      urls.maskActiveBase64 = await buildSparseOverlay(sparseActive);
    }

    return {
      imageBase64: urls.imageBase64 ?? null,
      maskAllBase64: urls.maskAllBase64 ?? null,
      maskActiveBase64: urls.maskActiveBase64 ?? null,
      maskRawBase64: urls.maskRawBase64 ?? null,
      zIndex: resolvedIndex,
      axis: resolvedAxis,
      total,
    };
  };

  const fetchSparseActiveMask = async ({
    sessionId,
    instanceId,
    axis,
    zIndex,
  }) => {
    const response = await apiClient.get("/eh/detection/instance-mask-sparse", {
      params: {
        session_id: sessionId,
        instance_id: instanceId,
        axis,
        z_index: zIndex,
      },
    });
    return response.data;
  };

  const buildSparseOverlay = (sparse) =>
    new Promise((resolve) => {
      if (!sparse || !sparse.mask_base64) {
        resolve(null);
        return;
      }

      const [minX, minY, maxX, maxY] = sparse.bbox || [0, 0, 0, 0];
      if (maxX <= minX && maxY <= minY) {
        resolve(null);
        return;
      }

      const maskImage = new Image();
      maskImage.onload = () => {
        const cropCanvas = document.createElement("canvas");
        cropCanvas.width = maskImage.width;
        cropCanvas.height = maskImage.height;
        const cropCtx = cropCanvas.getContext("2d");
        cropCtx.drawImage(maskImage, 0, 0);
        const cropData = cropCtx.getImageData(
          0,
          0,
          cropCanvas.width,
          cropCanvas.height,
        );

        const colorCanvas = document.createElement("canvas");
        colorCanvas.width = cropCanvas.width;
        colorCanvas.height = cropCanvas.height;
        const colorCtx = colorCanvas.getContext("2d");
        const colored = colorCtx.createImageData(
          cropCanvas.width,
          cropCanvas.height,
        );

        const [r, g, b] = sparse.color || [0, 255, 255];
        for (let i = 0; i < cropData.data.length; i += 4) {
          if (cropData.data[i] > 0) {
            colored.data[i] = r;
            colored.data[i + 1] = g;
            colored.data[i + 2] = b;
            colored.data[i + 3] = 255;
          }
        }
        colorCtx.putImageData(colored, 0, 0);

        const fullCanvas = document.createElement("canvas");
        fullCanvas.width = sparse.width || cropCanvas.width;
        fullCanvas.height = sparse.height || cropCanvas.height;
        const fullCtx = fullCanvas.getContext("2d");
        fullCtx.drawImage(colorCanvas, minX, minY);

        fullCanvas.toBlob((blob) => {
          if (!blob) {
            resolve(null);
            return;
          }
          resolve(URL.createObjectURL(blob));
        }, "image/png");
      };
      maskImage.onerror = () => resolve(null);
      maskImage.src = sparse.mask_base64;
    });

  const handleAxisChange = (nextAxis) => {
    const axisValue = nextAxis || "xy";
    setViewAxis(axisValue);
    localStorage.setItem("mask-proofreading-axis", axisValue);
    const axisIndex = getAxisIndexForInstance(activeInstance, axisValue);
    setViewState((prev) => ({ ...prev, zIndex: axisIndex, axis: axisValue }));
    setSliderZ(axisIndex);
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
      loadInstanceView(
        activeInstanceId,
        viewState.zIndex,
        false,
        undefined,
        viewAxis,
      );
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
                  sliderValue={sliderZ}
                  totalLayers={axisTotal || totalLayers}
                  axis={viewAxis}
                  axisOptions={axisOptions}
                  onAxisChange={handleAxisChange}
                  overlayAllAlpha={overlayAllAlpha}
                  overlayActiveAlpha={overlayActiveAlpha}
                  onPrevSlice={() =>
                    handleSliceCommit(Math.max(viewState.zIndex - 1, 0))
                  }
                  onNextSlice={() =>
                    handleSliceCommit(
                      Math.min(viewState.zIndex + 1, (axisTotal || totalLayers) - 1),
                    )
                  }
                  onSliceChange={handleSliceChange}
                  onSliceCommit={handleSliceCommit}
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
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 10px",
                  borderRadius: 10,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  fontSize: 12,
                }}
              >
                <Text type="secondary">
                  View {viewAxis.toUpperCase()} · Slice {viewState.zIndex + 1}
                </Text>
                <Text type="secondary">{axisTotal || totalLayers} total</Text>
              </div>
              <div
                style={{
                  display: "grid",
                  gap: 8,
                  paddingBottom: 4,
                  borderBottom: "1px solid #eef2f7",
                }}
              >
                <Text style={{ fontSize: 12, letterSpacing: 0.4 }} type="secondary">
                  REVIEW
                </Text>
                {activeInstance && instanceMode !== "none" && (
                  <>
                    <Text style={{ fontSize: 13, fontWeight: 600 }}>
                      Instance #{activeInstance.id}
                    </Text>
                    <Space size="small">
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
                  </>
                )}
              </div>

              <div
                style={{
                  display: "grid",
                  gap: 8,
                  paddingBottom: 4,
                  borderBottom: "1px solid #eef2f7",
                }}
              >
                <Text style={{ fontSize: 12, letterSpacing: 0.4 }} type="secondary">
                  VIEW
                </Text>
                <div>
                  <Text style={{ fontSize: 12 }}>All instances opacity</Text>
                  <Slider
                    min={0}
                    max={100}
                    value={Math.round(overlayAllAlpha * 100)}
                    onChange={(value) => setOverlayAllAlpha(value / 100)}
                  />
                  <Text style={{ fontSize: 12 }}>Active instance opacity</Text>
                  <Slider
                    min={0}
                    max={100}
                    value={Math.round(overlayActiveAlpha * 100)}
                    onChange={(value) => setOverlayActiveAlpha(value / 100)}
                  />
                </div>
              </div>

              {instanceMode !== "none" && instances.length > 0 && (
                <div style={{ display: "grid", gap: 8 }}>
                  <Text style={{ fontSize: 12, letterSpacing: 0.4 }} type="secondary">
                    INSTANCES
                  </Text>
                  <Space>
                    <Button size="small" onClick={goToPreviousInstance}>
                      Prev
                    </Button>
                    <Button size="small" onClick={goToNextInstance}>
                      Next
                    </Button>
                    <Button size="small" onClick={goToNextInstance}>
                      Next unreviewed
                    </Button>
                    <Button
                      size="small"
                      type="primary"
                      onClick={() => setShowInstanceBrowser(true)}
                    >
                      Browse…
                    </Button>
                  </Space>
                </div>
              )}

              <div
                style={{
                  display: "grid",
                  gap: 8,
                  paddingTop: 4,
                  borderTop: "1px solid #eef2f7",
                }}
              >
                <Text style={{ fontSize: 12, letterSpacing: 0.4 }} type="secondary">
                  PROGRESS
                </Text>
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
              </div>
            </div>
          </Sider>
        </Layout>
      </Content>

      {/* Editor is now inline to keep context */}
      <Drawer
        title="Browse instances"
        open={showInstanceBrowser}
        onClose={() => setShowInstanceBrowser(false)}
        width={380}
      >
        <InstanceNavigator
          instances={instances}
          activeInstanceId={activeInstanceId}
          onSelect={(inst) => {
            selectInstance(inst);
            setShowInstanceBrowser(false);
          }}
          onPrev={goToPreviousInstance}
          onNext={goToNextInstance}
          filterText={filterText}
          onFilterText={setFilterText}
          instanceMode={instanceMode}
        />
      </Drawer>
    </Layout>
  );
}

export default DetectionWorkflow;
