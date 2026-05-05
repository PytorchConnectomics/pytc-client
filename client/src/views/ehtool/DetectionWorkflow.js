import React, { useContext, useState, useEffect, useRef } from "react";
import {
  Card,
  Divider,
  Layout,
  message,
  Space,
  Typography,
  Button,
  Modal,
  Slider,
  InputNumber,
  Popover,
  Tag,
  Spin,
  Tooltip,
} from "antd";
import {
  ClearOutlined,
  DragOutlined,
  EditOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  SaveOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from "@ant-design/icons";
import DatasetLoader from "./DatasetLoader";
import InstanceNavigator from "./InstanceNavigator";
import ProofreadingEditor from "./ProofreadingEditor";
import Instance3DPreview from "./Instance3DPreview";
import SliceScheduler from "./SliceScheduler";
import {
  apiClient,
  getInstanceMeshPreview,
} from "../../api";
import { AppContext } from "../../contexts/GlobalContext";
import { useWorkflow } from "../../contexts/WorkflowContext";
import { logClientEvent } from "../../logging/appEventLog";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

const parsePositiveInt = (value, fallback) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const PREVIEW_MAX_DIM = parsePositiveInt(
  process.env.REACT_APP_EH_PREVIEW_MAX_DIM,
  384,
);
const THUMB_MAX_DIM = parsePositiveInt(
  process.env.REACT_APP_EH_THUMB_MAX_DIM,
  192,
);
const FILMSTRIP_BATCH_SIZE = parsePositiveInt(
  process.env.REACT_APP_EH_FILMSTRIP_BATCH_SIZE,
  12,
);
const PREVIEW_PREFETCH_RADIUS = parsePositiveInt(
  process.env.REACT_APP_EH_PREVIEW_PREFETCH_RADIUS,
  1,
);
const ENABLE_FILMSTRIP_PREVIEW =
  process.env.REACT_APP_EH_ENABLE_FILMSTRIP_PREVIEW !== "false";
const FAST_SCRUB_SLICES_PER_SEC = Number.parseFloat(
  process.env.REACT_APP_EH_FAST_SCRUB_SPS || "8",
);
const SCRUB_IDLE_MS = parsePositiveInt(
  process.env.REACT_APP_EH_SCRUB_IDLE_MS,
  120,
);
const WHEEL_SLICE_DELTA_PX = 72;
const WHEEL_SLICE_IDLE_MS = 140;
const DEFAULT_OVERLAY_ALL_ALPHA = 0.24;
const DEFAULT_OVERLAY_ACTIVE_ALPHA = 0.8;

const supportsAllInstanceOverlay = (mode) =>
  mode === "instance" || mode === "semantic";

const AXIS_LABELS = {
  xy: "XY",
  zy: "YZ",
  zx: "XZ",
};

const ORTHO_PANES = [
  { axis: "xy", label: "XY" },
  { axis: "zy", label: "YZ" },
  { axis: "zx", label: "XZ" },
];

const formatAxisLabel = (axis) => AXIS_LABELS[axis] || String(axis).toUpperCase();

function OrthoviewPane({
  axis,
  label,
  payload,
  loading,
  active,
  editable,
  onActivate,
  onSliceWheel,
  children,
}) {
  const rootRef = useRef(null);
  const wheelHandlerRef = useRef(onSliceWheel);

  useEffect(() => {
    wheelHandlerRef.current = onSliceWheel;
  }, [onSliceWheel]);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return undefined;
    const handleWheel = (event) => {
      if (!wheelHandlerRef.current || event.ctrlKey || event.metaKey) return;
      event.preventDefault();
      event.stopPropagation();
      wheelHandlerRef.current({
        deltaY: event.deltaY,
        deltaMode: event.deltaMode,
      });
    };
    node.addEventListener("wheel", handleWheel, {
      capture: true,
      passive: false,
    });
    return () => {
      node.removeEventListener("wheel", handleWheel, { capture: true });
    };
  }, []);

  return (
    <section
      ref={rootRef}
      onMouseDownCapture={() => {
        if (!active) onActivate?.();
      }}
      style={{
        minHeight: 0,
        position: "relative",
        display: "block",
        border: active ? "1px solid #64748b" : "1px solid #1f2937",
        borderRadius: 6,
        background: "#0f172a",
        overflow: "hidden",
        overscrollBehavior: "contain",
        touchAction: "none",
        boxShadow: "none",
      }}
    >
      <button
        type="button"
        onClick={onActivate}
        style={{
          position: "absolute",
          top: 8,
          left: 8,
          zIndex: 6,
          border: 0,
          borderRadius: 6,
          background: active
            ? "rgba(226, 232, 240, 0.94)"
            : "rgba(15, 23, 42, 0.66)",
          color: "#f8fafc",
          display: "inline-flex",
          alignItems: "center",
          minHeight: 24,
          padding: "3px 9px",
          cursor: active ? "default" : "pointer",
          textAlign: "left",
          boxShadow: active
            ? "0 0 0 1px rgba(148, 163, 184, 0.65), 0 6px 18px rgba(2, 6, 23, 0.22)"
            : "0 6px 18px rgba(2, 6, 23, 0.18)",
        }}
      >
        <span
          style={{
            fontWeight: 700,
            fontSize: 12,
            color: active ? "#0f172a" : "#f8fafc",
          }}
        >
          {label}
        </span>
      </button>
      <div style={{ position: "absolute", inset: 0, minHeight: 0 }}>
        {editable ? (
          children
        ) : payload?.imageBase64 ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              overflow: "hidden",
              background: "#0f172a",
            }}
          >
            <img
              src={payload.imageBase64}
              alt={`${label} slice`}
              draggable={false}
              style={{
                position: "absolute",
                maxWidth: "100%",
                maxHeight: "100%",
                imageRendering: "pixelated",
              }}
            />
            {payload.maskAllBase64 && (
              <img
                src={payload.maskAllBase64}
                alt=""
                draggable={false}
                style={{
                  position: "absolute",
                  maxWidth: "100%",
                  maxHeight: "100%",
                  imageRendering: "pixelated",
                  pointerEvents: "none",
                }}
              />
            )}
            {payload.maskActiveBase64 && (
              <img
                src={payload.maskActiveBase64}
                alt=""
                draggable={false}
                style={{
                  position: "absolute",
                  maxWidth: "100%",
                  maxHeight: "100%",
                  imageRendering: "pixelated",
                  pointerEvents: "none",
                }}
              />
            )}
          </div>
        ) : (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#cbd5e1",
              background: "#0f172a",
            }}
          >
            {loading ? <Spin /> : <span>{formatAxisLabel(axis)} preview</span>}
          </div>
        )}
        {!editable && loading && payload?.imageBase64 && (
          <div
            style={{
              position: "absolute",
              right: 10,
              bottom: 10,
              background: "rgba(15, 23, 42, 0.72)",
              borderRadius: 8,
              padding: 6,
            }}
          >
            <Spin size="small" />
          </div>
        )}
      </div>
    </section>
  );
}

function DetectionWorkflow({
  sessionId,
  setSessionId,
  refreshTrigger,
  workflowId,
}) {
  const appContext = useContext(AppContext);
  const workflowContext = useWorkflow();
  const pendingRuntimeAction = workflowContext?.pendingRuntimeAction;
  const consumeRuntimeAction = workflowContext?.consumeRuntimeAction;
  const activeWorkflow = workflowContext?.workflow;
  const [projectName, setProjectName] = useState("");
  const [totalLayers, setTotalLayers] = useState(0);
  const [instances, setInstances] = useState([]);
  const [instanceMode, setInstanceMode] = useState("none");
  const [activeInstanceId, setActiveInstanceId] = useState(null);
  const [activeInstance, setActiveInstance] = useState(null);
  const [filterText, setFilterText] = useState("");
  const [loadingInstances, setLoadingInstances] = useState(false);
  const [loadingView, setLoadingView] = useState(false);
  const [volumePreview, setVolumePreview] = useState(null);
  const [loadingVolumePreview, setLoadingVolumePreview] = useState(false);
  const [meshRevision, setMeshRevision] = useState(0);
  const [liveMaskDraft, setLiveMaskDraft] = useState(null);
  const [orthoviewPayloads, setOrthoviewPayloads] = useState({});
  const [loadingOrthoviews, setLoadingOrthoviews] = useState(false);
  const [activeToolState, setActiveToolState] = useState({
    tool: "paint",
    showMask: true,
    hasUnsavedEdits: false,
    zoom: 1,
    canEdit: true,
    activeBrushSize: 10,
  });
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
    instanceId: null,
  });
  const [sliderZ, setSliderZ] = useState(0);
  const [committedZ, setCommittedZ] = useState(0);
  const previewDebounceRef = useRef(null);
  const scrubIdleRef = useRef(null);
  const previewCache = useRef(new Map());
  const previewCacheOrder = useRef([]);
  const previewCacheLimit = 180;
  const filmstripBatchCache = useRef(new Map());
  const filmstripBatchCacheOrder = useRef([]);
  const filmstripBatchCacheLimit = 48;
  const filmstripFrameCache = useRef(new Map());
  const filmstripFrameCacheOrder = useRef([]);
  const filmstripFrameCacheLimit = 240;
  const isScrubbingRef = useRef(false);
  const scrubTrackRef = useRef({ zIndex: 0, at: 0 });
  const isFastScrubRef = useRef(false);
  const [overlayAllAlpha, setOverlayAllAlpha] = useState(
    DEFAULT_OVERLAY_ALL_ALPHA,
  );
  const [overlayActiveAlpha, setOverlayActiveAlpha] = useState(
    DEFAULT_OVERLAY_ACTIVE_ALPHA,
  );
  const [savingMask, setSavingMask] = useState(false);
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1440,
  );
  const [showQueue, setShowQueue] = useState(true);
  const [persistence, setPersistence] = useState(null);
  const lastPersistenceErrorRef = useRef(null);
  const lastFullRequestKeyRef = useRef(null);
  const fullRequestInFlightRef = useRef(null);
  const lastProofreadingLogRef = useRef({});
  const orthoviewPayloadsRef = useRef({});
  const editorRefs = useRef({});
  const sliceWheelRef = useRef({});

  const schedulerRef = useRef(
    new SliceScheduler({
      interactiveConcurrency: 1,
      nearbyConcurrency: 1,
      backgroundConcurrency: 1,
    }),
  );
  const viewCache = useRef(new Map());
  const viewCacheOrder = useRef([]);
  const viewCacheLimit = 80;
  const handledRuntimeActionIdsRef = useRef(new Set());

  const ensurePerfState = () => {
    if (typeof window === "undefined") return null;
    const current = window.__proofreadPerf;
    if (current) return current;
    const next = {
      events: [],
      counters: {},
      timings: {},
    };
    window.__proofreadPerf = next;
    return next;
  };

  const summarizeSamples = (samples) => {
    if (!samples.length) return { median: 0, p95: 0 };
    const sorted = [...samples].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    const median =
      sorted.length % 2 === 0
        ? Number(((sorted[mid - 1] + sorted[mid]) / 2).toFixed(1))
        : Number(sorted[mid].toFixed(1));
    const p95Index = Math.max(0, Math.ceil(sorted.length * 0.95) - 1);
    const p95 = Number(sorted[p95Index].toFixed(1));
    return { median, p95 };
  };

  const perfLog = (label, startAt) => {
    if (typeof window === "undefined") return;
    const duration = Number((performance.now() - startAt).toFixed(1));
    const perfState = ensurePerfState();
    if (!perfState) return;
    perfState.events.push({ label, duration, at: Date.now() });
    if (perfState.events.length > 400) {
      perfState.events.shift();
    }
    perfState.counters[label] = (perfState.counters[label] || 0) + 1;
    const timing = perfState.timings[label] || { samples: [] };
    timing.samples.push(duration);
    if (timing.samples.length > 300) {
      timing.samples.shift();
    }
    const stats = summarizeSamples(timing.samples);
    timing.median = stats.median;
    timing.p95 = stats.p95;
    timing.last = duration;
    perfState.timings[label] = timing;
    window.__proofreadPerf = perfState;
  };

  const perfCount = (label) => {
    if (typeof window === "undefined") return;
    const perfState = ensurePerfState();
    if (!perfState) return;
    perfState.counters[label] = (perfState.counters[label] || 0) + 1;
    window.__proofreadPerf = perfState;
  };

  const logProofreadingEvent = (event, data = {}, options = {}) => {
    const now =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    const throttleMs = Number.isFinite(options.throttleMs)
      ? options.throttleMs
      : 0;
    const throttleKey = options.throttleKey || event;
    if (
      throttleMs > 0 &&
      lastProofreadingLogRef.current[throttleKey] &&
      now - lastProofreadingLogRef.current[throttleKey] < throttleMs
    ) {
      return;
    }
    lastProofreadingLogRef.current[throttleKey] = now;
    logClientEvent(event, {
      level: options.level || "INFO",
      message: options.message || event,
      source: "proofreading",
      data: {
        sessionId,
        activeInstanceId,
        axis: viewAxis,
        sliderZ,
        committedZ,
        ...data,
      },
    });
  };

  const getErrorMessage = (error, fallback) => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      if (detail.msg) return detail.msg;
      try {
        return JSON.stringify(detail);
      } catch (err) {
        return fallback;
      }
    }
    return fallback;
  };

  const getAxisIndexForInstance = (instance, axis) => {
    if (!instance) return 0;
    if (axis === "zx") return instance.com_y ?? 0;
    if (axis === "zy") return instance.com_x ?? 0;
    return instance.com_z ?? 0;
  };

  const clampAlpha = (value, fallback) => {
    const numeric = Number(value);
    if (Number.isNaN(numeric)) return fallback;
    return Math.min(Math.max(numeric, 0), 1);
  };

  useEffect(() => {
    if (sessionId) {
      loadInstances();
    }
  }, [sessionId, refreshTrigger]);

  useEffect(() => {
    if (!sessionId || !activeInstanceId) {
      setVolumePreview(null);
      setLiveMaskDraft(null);
      return undefined;
    }
    let cancelled = false;
    setLoadingVolumePreview(true);
    setLiveMaskDraft(null);
    getInstanceMeshPreview(sessionId, activeInstanceId, 60000)
      .then((preview) => {
        if (!cancelled) setVolumePreview(preview || null);
      })
      .catch((error) => {
        if (!cancelled) {
          console.warn("Failed to load 3D instance preview:", error);
          setVolumePreview(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingVolumePreview(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeInstanceId, meshRevision, sessionId]);

  useEffect(() => {
    const persistenceError = persistence?.last_error;
    if (!persistenceError) return;
    if (lastPersistenceErrorRef.current === persistenceError) return;
    lastPersistenceErrorRef.current = persistenceError;
    Modal.error({
      title: "Persistence error",
      content: persistenceError,
      okText: "OK",
    });
  }, [persistence?.last_error]);

  useEffect(() => {
    const scheduler = schedulerRef.current;
    return () => {
      scheduler.clear();
      clearSliceWheelTimers();
      if (previewDebounceRef.current) {
        clearTimeout(previewDebounceRef.current);
      }
      if (scrubIdleRef.current) {
        clearTimeout(scrubIdleRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const lockViewerWheel = (event) => {
      if (!event.target?.closest?.("[data-proofreader-wheel-lock='true']")) {
        return;
      }
      event.preventDefault();
    };
    document.addEventListener("wheel", lockViewerWheel, {
      capture: true,
      passive: false,
    });
    return () => {
      document.removeEventListener("wheel", lockViewerWheel, { capture: true });
    };
  }, []);

  useEffect(() => {
    if (
      !sessionId ||
      !activeInstanceId ||
      !supportsAllInstanceOverlay(instanceMode)
    )
      return;
    if (isScrubbingRef.current) return;
    const includeAll = overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
    const needsAll = includeAll && !viewState.maskAllBase64;
    const needsActive = includeActive && !viewState.maskActiveBase64;
    if (needsAll || needsActive) {
      const overlayRequestIdentity = [
        activeInstanceId,
        viewAxis,
        committedZ,
        includeAll ? "all" : "noall",
        includeActive ? "active" : "noactive",
        "raw",
      ].join(":");
      if (
        lastFullRequestKeyRef.current === overlayRequestIdentity ||
        fullRequestInFlightRef.current === overlayRequestIdentity
      ) {
        return;
      }
      loadInstanceView(activeInstanceId, committedZ, true, undefined, viewAxis);
    }
    if (overlayAllAlpha <= 0.001 && viewState.maskAllBase64) {
      setViewState((prev) => ({ ...prev, maskAllBase64: null }));
    }
    if (overlayActiveAlpha <= 0.001 && viewState.maskActiveBase64) {
      setViewState((prev) => ({ ...prev, maskActiveBase64: null }));
    }
  }, [
    overlayAllAlpha,
    overlayActiveAlpha,
    sessionId,
    activeInstanceId,
    instanceMode,
    committedZ,
    viewAxis,
    viewState.maskAllBase64,
    viewState.maskActiveBase64,
  ]);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!sessionId || !activeInstanceId) return;
    if (isScrubbingRef.current) return;
    const includeAll =
      supportsAllInstanceOverlay(instanceMode) && overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
    const requestIdentity = [
      activeInstanceId,
      viewAxis,
      committedZ,
      includeAll ? "all" : "noall",
      includeActive ? "active" : "noactive",
      "raw",
    ].join(":");
    const hasCommittedView =
      viewState.axis === viewAxis &&
      viewState.zIndex === committedZ &&
      Boolean(viewState.imageBase64) &&
      Boolean(viewState.maskRawBase64) &&
      (!includeAll || Boolean(viewState.maskAllBase64)) &&
      (!includeActive || Boolean(viewState.maskActiveBase64));
    if (hasCommittedView) return;
    if (fullRequestInFlightRef.current === requestIdentity) return;
    loadInstanceView(activeInstanceId, committedZ, true, undefined, viewAxis);
  }, [
    sessionId,
    activeInstanceId,
    viewAxis,
    committedZ,
    instanceMode,
    overlayAllAlpha,
    overlayActiveAlpha,
    viewState.axis,
    viewState.zIndex,
    viewState.imageBase64,
    viewState.maskRawBase64,
    viewState.maskAllBase64,
    viewState.maskActiveBase64,
  ]);

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
          handleAxisChange("zy");
          break;
        case "3":
          handleAxisChange("zx");
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

  const handleDatasetLoad = async (datasetPath, maskPath, projectName) => {
    setLoadingInstances(true);
    try {
      logProofreadingEvent("proofreading_dataset_load_started", {
        datasetPath,
        maskPath,
        projectName,
      });
      const response = await apiClient.post("/eh/detection/load", {
        dataset_path: datasetPath,
        mask_path: maskPath || null,
        project_name: projectName,
        workflow_id: workflowId || null,
      });

      setSessionId(response.data.session_id);
      setProjectName(response.data.project_name);
      setTotalLayers(response.data.total_layers);
      logProofreadingEvent("proofreading_dataset_load_completed", {
        nextSessionId: response.data.session_id,
        totalLayers: response.data.total_layers,
        projectName: response.data.project_name,
      });
      message.success(
        `Loaded ${response.data.total_layers} slices successfully`,
      );
      await loadInstances(response.data.session_id, true);
    } catch (error) {
      console.error("Failed to load dataset:", error);
      logProofreadingEvent(
        "proofreading_dataset_load_failed",
        { error: getErrorMessage(error, "Failed to load dataset") },
        { level: "ERROR" },
      );
      Modal.error({
        title: "Dataset load failed",
        content: getErrorMessage(
          error,
          "Unable to load this dataset. Verify paths and mask availability, then retry.",
        ),
        okText: "OK",
      });
    } finally {
      setLoadingInstances(false);
    }
  };

  useEffect(() => {
    if (pendingRuntimeAction?.kind !== "start_proofreading") return;
    const action = pendingRuntimeAction;
    const actionKey =
      action.id ||
      `${action.kind}:${action.created_at || action.createdAt || JSON.stringify(action.overrides || {})}`;
    if (handledRuntimeActionIdsRef.current.has(actionKey)) return;
    handledRuntimeActionIdsRef.current.add(actionKey);
    consumeRuntimeAction?.(action.id);
    if (sessionId) return;

    const overrides = action.overrides || {};
    const datasetPath =
      overrides.datasetPath ||
      activeWorkflow?.image_path ||
      activeWorkflow?.dataset_path ||
      activeWorkflow?.inference_output_path ||
      "";
    const maskPath =
      overrides.maskPath ||
      activeWorkflow?.mask_path ||
      activeWorkflow?.inference_output_path ||
      activeWorkflow?.corrected_mask_path ||
      activeWorkflow?.label_path ||
      "";
    const nextProjectName =
      overrides.projectName || activeWorkflow?.title || "Proofreading review";

    if (!datasetPath) {
      message.warning("Choose image data before proofreading.");
      return;
    }

    handleDatasetLoad(datasetPath, maskPath, nextProjectName);
    // Runtime actions are one-shot messages consumed above; handleDatasetLoad is
    // intentionally not a dependency because it is defined in this large legacy component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeWorkflow?.corrected_mask_path,
    activeWorkflow?.dataset_path,
    activeWorkflow?.image_path,
    activeWorkflow?.inference_output_path,
    activeWorkflow?.label_path,
    activeWorkflow?.mask_path,
    activeWorkflow?.title,
    consumeRuntimeAction,
    pendingRuntimeAction,
    sessionId,
  ]);

  const isAbortError = (error) => {
    if (!error) return false;
    return (
      error.name === "AbortError" ||
      error.code === "ERR_CANCELED" ||
      error.message === "canceled" ||
      error.message === "stale-request"
    );
  };

  const revokePayloadUrls = (payload) => {
    if (!payload) return;
    const frameUrls = new Set(filmstripFrameCache.current.values());
    [
      payload.imageBase64,
      payload.maskAllBase64,
      payload.maskActiveBase64,
      payload.maskRawBase64,
    ]
      .filter((url) => typeof url === "string" && url.startsWith("blob:"))
      .forEach((url) => {
        if (!frameUrls.has(url)) {
          URL.revokeObjectURL(url);
        }
      });
  };

  const clearFrameCaches = () => {
    viewCache.current.forEach((cached) => revokePayloadUrls(cached));
    previewCache.current.forEach((cached) => revokePayloadUrls(cached));
    filmstripFrameCache.current.forEach((url) => {
      if (typeof url === "string" && url.startsWith("blob:")) {
        URL.revokeObjectURL(url);
      }
    });
    viewCache.current.clear();
    previewCache.current.clear();
    filmstripBatchCache.current.clear();
    filmstripFrameCache.current.clear();
    viewCacheOrder.current = [];
    previewCacheOrder.current = [];
    filmstripBatchCacheOrder.current = [];
    filmstripFrameCacheOrder.current = [];
    logProofreadingEvent(
      "proofreading_frame_caches_cleared",
      {},
      { throttleMs: 1000 },
    );
  };

  useEffect(() => {
    return () => {
      clearFrameCaches();
      Object.values(orthoviewPayloadsRef.current).forEach((payload) =>
        revokePayloadUrls(payload),
      );
      orthoviewPayloadsRef.current = {};
    };
  }, []);

  const touchCacheOrder = (order, key) => {
    const idx = order.indexOf(key);
    if (idx >= 0) order.splice(idx, 1);
    order.push(key);
  };

  const clampSliceIndex = (value, totalForAxis) => {
    const maxIndex = Math.max((totalForAxis || 1) - 1, 0);
    return Math.max(0, Math.min(Number(value) || 0, maxIndex));
  };

  const buildCacheKey = ({
    instanceId,
    axis,
    zIndex,
    includeAll,
    includeActive,
    quality,
    includeRaw = false,
  }) =>
    [
      instanceId,
      axis,
      zIndex,
      includeAll ? "all" : "noall",
      includeActive ? "active" : "noactive",
      includeRaw ? "raw" : "noraw",
      quality,
    ].join(":");

  const buildFilmstripBatchKey = ({
    sessionId: sid,
    instanceId,
    axis,
    batchStart,
    zCount,
    kind,
    maxDim,
    quality,
  }) =>
    [
      sid,
      instanceId,
      axis,
      batchStart,
      zCount,
      kind,
      maxDim || "full",
      quality,
    ].join(":");

  const cacheFilmstripBatch = (key, batch) => {
    const existing = filmstripBatchCache.current.get(key);
    if (existing && existing !== batch) {
      const prefix = `${key}:`;
      filmstripFrameCache.current.forEach((_, frameKey) => {
        if (!frameKey.startsWith(prefix)) return;
        filmstripFrameCache.current.delete(frameKey);
      });
      filmstripFrameCacheOrder.current =
        filmstripFrameCacheOrder.current.filter(
          (frameKey) => !frameKey.startsWith(prefix),
        );
    }
    filmstripBatchCache.current.set(key, batch);
    touchCacheOrder(filmstripBatchCacheOrder.current, key);
    while (filmstripBatchCacheOrder.current.length > filmstripBatchCacheLimit) {
      const oldest = filmstripBatchCacheOrder.current.shift();
      filmstripBatchCache.current.delete(oldest);
      const prefix = `${oldest}:`;
      filmstripFrameCache.current.forEach((_, frameKey) => {
        if (!frameKey.startsWith(prefix)) return;
        filmstripFrameCache.current.delete(frameKey);
      });
      filmstripFrameCacheOrder.current =
        filmstripFrameCacheOrder.current.filter(
          (frameKey) => !frameKey.startsWith(prefix),
        );
    }
  };

  const cacheFilmstripFrame = (key, frameUrl) => {
    filmstripFrameCache.current.set(key, frameUrl);
    touchCacheOrder(filmstripFrameCacheOrder.current, key);
    while (filmstripFrameCacheOrder.current.length > filmstripFrameCacheLimit) {
      const oldest = filmstripFrameCacheOrder.current.shift();
      filmstripFrameCache.current.delete(oldest);
    }
  };

  const cachePreview = (key, payload) => {
    const existing = previewCache.current.get(key);
    if (existing && existing !== payload) {
      revokePayloadUrls(existing);
    }
    previewCache.current.set(key, payload);
    touchCacheOrder(previewCacheOrder.current, key);
    while (previewCacheOrder.current.length > previewCacheLimit) {
      const oldest = previewCacheOrder.current.shift();
      const cached = previewCache.current.get(oldest);
      previewCache.current.delete(oldest);
      revokePayloadUrls(cached);
    }
  };

  const cacheView = (key, payload) => {
    const existing = viewCache.current.get(key);
    if (existing && existing !== payload) {
      revokePayloadUrls(existing);
    }
    viewCache.current.set(key, payload);
    touchCacheOrder(viewCacheOrder.current, key);
    while (viewCacheOrder.current.length > viewCacheLimit) {
      const oldest = viewCacheOrder.current.shift();
      const cached = viewCache.current.get(oldest);
      viewCache.current.delete(oldest);
      revokePayloadUrls(cached);
    }
  };

  const setPreviewView = (payload) => {
    if (!payload) return;
    setViewState((prev) => ({
      ...prev,
      imageBase64: payload.imageBase64 ?? prev.imageBase64,
      // Keep last-known overlays during scrub so the viewport does not flash
      // blank between preview frames.
      maskAllBase64: payload.maskAllBase64 ?? prev.maskAllBase64,
      maskActiveBase64: payload.maskActiveBase64 ?? prev.maskActiveBase64,
      maskRawBase64:
        payload.maskRawBase64 ??
        (payload.zIndex === prev.zIndex &&
        payload.axis === prev.axis &&
        payload.instanceId === prev.instanceId
          ? prev.maskRawBase64
          : null),
      zIndex: payload.zIndex,
      axis: payload.axis,
      total: payload.total,
      instanceId: payload.instanceId ?? prev.instanceId,
    }));
    setAxisTotal(payload.total);
  };

  const createAbortError = () => {
    const abortError = new Error("aborted");
    abortError.name = "AbortError";
    return abortError;
  };

  const extractFilmstripFrameBlob = async ({
    blob,
    frameIndex,
    frameCount,
    signal,
    frameCachePrefix,
  }) => {
    if (!blob) return null;
    if (signal?.aborted) throw createAbortError();
    const safeCount = Math.max(1, Number(frameCount) || 1);
    const safeIndex = Math.max(0, Math.min(frameIndex, safeCount - 1));
    const frameCacheKey = frameCachePrefix
      ? `${frameCachePrefix}:${safeIndex}`
      : null;
    if (frameCacheKey) {
      const cachedFrame = filmstripFrameCache.current.get(frameCacheKey);
      if (cachedFrame) return cachedFrame;
    }

    const encodeBitmapToObjectUrl = (bitmap, outputType) =>
      new Promise((resolve, reject) => {
        const canvas = document.createElement("canvas");
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(bitmap, 0, 0);
        canvas.toBlob(
          (frameBlob) => {
            if (!frameBlob) {
              reject(new Error("Failed to create filmstrip frame"));
              return;
            }
            resolve(URL.createObjectURL(frameBlob));
          },
          outputType || "image/png",
          0.9,
        );
      });

    let frameUrl = null;
    if (safeCount <= 1) {
      frameUrl = URL.createObjectURL(blob);
    } else if (typeof createImageBitmap === "function") {
      const probe = await createImageBitmap(blob);
      const fullWidth = probe.width;
      const fullHeight = probe.height;
      probe.close?.();
      const frameHeight = Math.max(1, Math.floor(fullHeight / safeCount));
      const sourceY = Math.max(
        0,
        Math.min(
          safeIndex * frameHeight,
          Math.max(fullHeight - frameHeight, 0),
        ),
      );
      const croppedBitmap = await createImageBitmap(
        blob,
        0,
        sourceY,
        fullWidth,
        frameHeight,
      );
      try {
        if (signal?.aborted) throw createAbortError();
        frameUrl = await encodeBitmapToObjectUrl(croppedBitmap, blob.type);
      } finally {
        croppedBitmap.close?.();
      }
    } else {
      const sourceUrl = URL.createObjectURL(blob);
      try {
        const image = await new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = () =>
            reject(new Error("Failed to decode filmstrip image"));
          img.src = sourceUrl;
        });
        const frameHeight = Math.max(1, Math.floor(image.height / safeCount));
        const sourceY = Math.max(
          0,
          Math.min(
            safeIndex * frameHeight,
            Math.max(image.height - frameHeight, 0),
          ),
        );
        const canvas = document.createElement("canvas");
        canvas.width = image.width;
        canvas.height = frameHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(
          image,
          0,
          sourceY,
          image.width,
          frameHeight,
          0,
          0,
          image.width,
          frameHeight,
        );
        frameUrl = await new Promise((resolve, reject) => {
          canvas.toBlob(
            (frameBlob) => {
              if (!frameBlob) {
                reject(new Error("Failed to create filmstrip frame"));
                return;
              }
              resolve(URL.createObjectURL(frameBlob));
            },
            blob.type || "image/png",
            0.9,
          );
        });
      } finally {
        URL.revokeObjectURL(sourceUrl);
      }
    }

    if (frameCacheKey && frameUrl) {
      cacheFilmstripFrame(frameCacheKey, frameUrl);
    }
    return frameUrl;
  };

  const fetchInstanceBundle = async ({
    sessionId,
    instanceId,
    axis,
    zIndex,
    kinds,
    maxDim,
    quality = "full",
    signal,
    preferWebp = false,
  }) => {
    const requests = kinds.map((kind) =>
      apiClient.get("/eh/detection/instance-image", {
        params: {
          session_id: sessionId,
          instance_id: instanceId,
          axis,
          z_index: zIndex,
          kind,
          max_dim: maxDim || undefined,
          quality,
          format: kind === "image" && preferWebp ? "webp" : "png",
        },
        responseType: "blob",
        signal,
      }),
    );

    const responses = requests.length ? await Promise.all(requests) : [];
    const metaResponse = responses[0];
    const resolvedIndex = Number(
      metaResponse?.headers?.["x-z-index"] ?? zIndex ?? 0,
    );
    const total = Number(
      metaResponse?.headers?.["x-total-layers"] ?? totalLayers ?? 0,
    );
    const resolvedAxis = metaResponse?.headers?.["x-axis"] ?? axis;

    const payload = {
      imageBase64: null,
      maskAllBase64: null,
      maskActiveBase64: null,
      maskRawBase64: null,
      zIndex: resolvedIndex,
      axis: resolvedAxis,
      total,
      instanceId,
      batchStart: resolvedIndex,
      batchCount: 1,
      quality,
      kindSet: kinds,
    };

    responses.forEach((response, idx) => {
      const kind = kinds[idx];
      const url = URL.createObjectURL(response.data);
      if (kind === "image") payload.imageBase64 = url;
      if (kind === "mask_all") payload.maskAllBase64 = url;
      if (kind === "mask_active") payload.maskActiveBase64 = url;
      if (kind === "mask_active_binary") payload.maskRawBase64 = url;
    });

    return payload;
  };

  const fetchFilmstripBundle = async ({
    sessionId,
    instanceId,
    axis,
    zIndex,
    kinds,
    maxDim,
    quality = "preview",
    signal,
  }) => {
    const requestedStart =
      Math.floor(Math.max(zIndex, 0) / FILMSTRIP_BATCH_SIZE) *
      FILMSTRIP_BATCH_SIZE;
    const requestedCount = FILMSTRIP_BATCH_SIZE;
    const entriesByKind = new Map();
    const missingKinds = [];

    kinds.forEach((kind) => {
      const batchKey = buildFilmstripBatchKey({
        sessionId,
        instanceId,
        axis,
        batchStart: requestedStart,
        zCount: requestedCount,
        kind,
        maxDim,
        quality,
      });
      const cached = filmstripBatchCache.current.get(batchKey);
      if (cached) {
        entriesByKind.set(kind, { key: batchKey, ...cached });
      } else {
        missingKinds.push({ kind, key: batchKey });
      }
    });

    if (missingKinds.length > 0) {
      const responses = await Promise.all(
        missingKinds.map(({ kind }) =>
          apiClient.get("/eh/detection/instance-filmstrip", {
            params: {
              session_id: sessionId,
              instance_id: instanceId,
              axis,
              z_start: requestedStart,
              z_count: requestedCount,
              kind,
              max_dim: maxDim || undefined,
              quality,
              format: kind === "image" ? "webp" : "png",
            },
            responseType: "blob",
            signal,
          }),
        ),
      );

      responses.forEach((response, idx) => {
        const { kind, key } = missingKinds[idx];
        const entry = {
          blob: response.data,
          meta: {
            zStart: Number(response?.headers?.["x-z-start"] ?? requestedStart),
            zCount: Number(
              response?.headers?.["x-z-count"] ?? FILMSTRIP_BATCH_SIZE,
            ),
            total: Number(
              response?.headers?.["x-total-layers"] ?? totalLayers ?? 0,
            ),
            axis: response?.headers?.["x-axis"] ?? axis,
            frameHeight:
              Number(response?.headers?.["x-frame-height"] ?? 0) || null,
          },
        };
        cacheFilmstripBatch(key, entry);
        entriesByKind.set(kind, { key, ...entry });
      });
    }

    const firstEntry = entriesByKind.get(kinds[0]);
    const meta = firstEntry?.meta;
    const resolvedStart = Number(meta?.zStart ?? requestedStart);
    const resolvedCount = Number(meta?.zCount ?? requestedCount);
    const total = Number(meta?.total ?? totalLayers ?? 0);
    const resolvedAxis = meta?.axis ?? axis;
    const frameOffset = Math.max(
      0,
      Math.min(zIndex - resolvedStart, Math.max(resolvedCount - 1, 0)),
    );

    const payload = {
      imageBase64: null,
      maskAllBase64: null,
      maskActiveBase64: null,
      maskRawBase64: null,
      zIndex: resolvedStart + frameOffset,
      axis: resolvedAxis,
      total,
      instanceId,
      batchStart: resolvedStart,
      batchCount: resolvedCount,
      quality,
      kindSet: kinds,
    };

    for (let idx = 0; idx < kinds.length; idx += 1) {
      const kind = kinds[idx];
      const entry = entriesByKind.get(kind);
      if (!entry?.blob) continue;
      const frameUrl = await extractFilmstripFrameBlob({
        blob: entry.blob,
        frameIndex: frameOffset,
        frameCount: resolvedCount,
        signal,
        frameCachePrefix: entry.key,
      });
      if (kind === "image") payload.imageBase64 = frameUrl;
      if (kind === "mask_all") payload.maskAllBase64 = frameUrl;
      if (kind === "mask_active") payload.maskActiveBase64 = frameUrl;
      if (kind === "mask_active_binary") payload.maskRawBase64 = frameUrl;
    }

    return payload;
  };

  const fetchPreviewPayload = async ({
    sessionId,
    instanceId,
    axis,
    zIndex,
    includeAll,
    includeActive,
    imageOnly = false,
    maxDim = PREVIEW_MAX_DIM,
    preferFilmstrip = ENABLE_FILMSTRIP_PREVIEW,
    signal,
  }) => {
    const kinds = ["image", "mask_active_binary"];
    if (!imageOnly) {
      if (includeActive) kinds.push("mask_active");
      if (includeAll) kinds.push("mask_all");
    }

    const quality = "preview";

    if (preferFilmstrip) {
      try {
        return await fetchFilmstripBundle({
          sessionId,
          instanceId,
          axis,
          zIndex,
          kinds,
          maxDim,
          quality,
          signal,
        });
      } catch (error) {
        if (isAbortError(error)) throw error;
      }
    }

    return fetchInstanceBundle({
      sessionId,
      instanceId,
      axis,
      zIndex,
      kinds,
      maxDim,
      quality,
      signal,
      preferWebp: true,
    });
  };

  const loadInstances = async (overrideSessionId, forceView = false) => {
    const sessionToUse = overrideSessionId ?? sessionId;
    if (!sessionToUse) return;
    setLoadingInstances(true);
    schedulerRef.current.clear();
    clearFrameCaches();
    try {
      const response = await apiClient.get("/eh/detection/instances", {
        params: { session_id: sessionToUse },
      });

      const instanceList = response.data.instances || [];
      const nextInstanceMode = response.data.instance_mode || "none";
      const nextTotalLayers = response.data.total_layers || 0;
      const uiState = response.data.ui_state || null;
      const persistenceStatus = response.data.persistence || null;
      const shouldRestore = forceView || !activeInstanceId;
      const storedAxis =
        uiState && ["xy", "zx", "zy"].includes(uiState.axis)
          ? uiState.axis
          : null;
      const axisToUse =
        storedAxis && shouldRestore ? storedAxis : viewAxis || "xy";

      setInstances(instanceList);
      setInstanceMode(nextInstanceMode);
      setTotalLayers(nextTotalLayers);
      setAxisTotal(nextTotalLayers);
      setPersistence(persistenceStatus);

      let nextOverlayAllAlpha =
        uiState && shouldRestore
          ? clampAlpha(uiState.overlay_all_alpha, overlayAllAlpha)
          : overlayAllAlpha;
      let nextOverlayActiveAlpha =
        uiState && shouldRestore
          ? clampAlpha(uiState.overlay_active_alpha, overlayActiveAlpha)
          : overlayActiveAlpha;
      let overlayVisibilityChanged = false;

      if (
        shouldRestore &&
        nextInstanceMode !== "none"
      ) {
        if (
          nextOverlayAllAlpha <= 0.001 &&
          nextOverlayActiveAlpha <= 0.001
        ) {
          nextOverlayAllAlpha = DEFAULT_OVERLAY_ALL_ALPHA;
          nextOverlayActiveAlpha = DEFAULT_OVERLAY_ACTIVE_ALPHA;
          overlayVisibilityChanged = true;
        } else {
          if (
            supportsAllInstanceOverlay(nextInstanceMode) &&
            nextOverlayAllAlpha > 0.001 &&
            nextOverlayAllAlpha < DEFAULT_OVERLAY_ALL_ALPHA
          ) {
            nextOverlayAllAlpha = DEFAULT_OVERLAY_ALL_ALPHA;
            overlayVisibilityChanged = true;
          }
          if (
            nextOverlayActiveAlpha > 0.001 &&
            nextOverlayActiveAlpha < DEFAULT_OVERLAY_ACTIVE_ALPHA
          ) {
            nextOverlayActiveAlpha = DEFAULT_OVERLAY_ACTIVE_ALPHA;
            overlayVisibilityChanged = true;
          }
        }
      }

      if (shouldRestore || overlayVisibilityChanged) {
        setOverlayAllAlpha(nextOverlayAllAlpha);
        setOverlayActiveAlpha(nextOverlayActiveAlpha);
      }

      setViewAxis(axisToUse);

      const firstUnreviewed = instanceList.find(
        (inst) => inst.classification === "error",
      );
      const fallbackInstance = firstUnreviewed || instanceList[0] || null;
      const storedInstance =
        uiState && uiState.last_instance_id
          ? instanceList.find((inst) => inst.id === uiState.last_instance_id)
          : null;
      const initialInstance = shouldRestore
        ? storedInstance || fallbackInstance
        : activeInstance || fallbackInstance;

      if (initialInstance) {
        const axisIndex = getAxisIndexForInstance(initialInstance, axisToUse);
        const storedIndex = Number.isFinite(uiState?.last_slice_index)
          ? clampSliceIndex(uiState.last_slice_index, nextTotalLayers)
          : axisIndex;
        const resolvedIndex = shouldRestore ? storedIndex : axisIndex;
        setActiveInstanceId(initialInstance.id);
        setActiveInstance(initialInstance);
        setViewState((prev) => ({
          ...prev,
          zIndex: resolvedIndex,
          axis: axisToUse,
          total: nextTotalLayers,
          instanceId: initialInstance.id,
          imageBase64: null,
          maskAllBase64: null,
          maskActiveBase64: null,
          maskRawBase64: null,
        }));
        setSliderZ(resolvedIndex);
        setCommittedZ(resolvedIndex);
      } else {
        setActiveInstanceId(null);
        setActiveInstance(null);
      }
    } catch (error) {
      console.error("Failed to load instances:", error);
      message.error(getErrorMessage(error, "Failed to load instances"));
    } finally {
      setLoadingInstances(false);
    }
  };

  const refreshPersistenceStatus = async (overrideSessionId) => {
    const sessionToUse = overrideSessionId ?? sessionId;
    if (!sessionToUse) return;
    try {
      const response = await apiClient.get("/eh/detection/persistence-status", {
        params: { session_id: sessionToUse },
      });
      setPersistence(response.data?.persistence || null);
    } catch (error) {
      console.warn("Failed to refresh persistence status:", error);
    }
  };

  const prefetchAdjacent = async (
    instanceId,
    zIndex,
    sessionToUse,
    axisToUse,
    axisTotalValue,
    includeAll,
    includeActive,
    includeRaw,
  ) => {
    const totalForAxis = axisTotalValue || axisTotal || totalLayers;
    if (!sessionToUse || !totalForAxis) return;
    const neighbors = Array.from(
      new Set([
        Math.max(zIndex - 1, 0),
        Math.min(zIndex + 1, totalForAxis - 1),
      ]),
    );
    const kinds = ["image", "mask_active_binary"];
    if (includeActive) kinds.push("mask_active");
    if (includeAll) kinds.push("mask_all");
    if (includeRaw) kinds.push("mask_active_binary");

    await Promise.allSettled(
      neighbors.map((neighbor) => {
        const key = buildCacheKey({
          instanceId,
          axis: axisToUse,
          zIndex: neighbor,
          includeAll,
          includeActive,
          quality: "full",
        });
        if (viewCache.current.has(key)) return Promise.resolve();
        const lane = `prefetch-full:${instanceId}:${axisToUse}:${neighbor}`;
        return schedulerRef.current
          .run({
            key: `${lane}:${key}`,
            lane: "background",
            scope: `prefetch-full:${instanceId}:${axisToUse}`,
            priority: 10,
            exec: (signal) =>
              fetchInstanceBundle({
                sessionId: sessionToUse,
                instanceId,
                axis: axisToUse,
                zIndex: neighbor,
                kinds,
                maxDim: null,
                quality: "full",
                signal,
              }),
          })
          .then((payload) => {
            cacheView(key, payload);
          })
          .catch(() => {});
      }),
    );
  };

  const prefetchPreviewNeighbors = async (
    instanceId,
    zIndex,
    axisToUse,
    includeAll,
    includeActive,
    maxDim = PREVIEW_MAX_DIM,
    qualityLabel = `preview-${PREVIEW_MAX_DIM}`,
    distance = 1,
    imageOnly = false,
  ) => {
    const totalForAxis = axisTotal || totalLayers;
    if (!sessionId || !totalForAxis) return;
    const neighborSet = new Set();
    for (let offset = 1; offset <= distance; offset += 1) {
      neighborSet.add(Math.max(zIndex - offset, 0));
      neighborSet.add(Math.min(zIndex + offset, totalForAxis - 1));
    }
    const neighbors = Array.from(neighborSet);

    await Promise.allSettled(
      neighbors.map((neighbor) => {
        const key = buildCacheKey({
          instanceId,
          axis: axisToUse,
          zIndex: neighbor,
          includeAll,
          includeActive,
          quality: qualityLabel,
        });
        if (previewCache.current.has(key)) return Promise.resolve();
        const lane = `prefetch-preview:${instanceId}:${axisToUse}:${neighbor}`;
        return schedulerRef.current
          .run({
            key: `${lane}:${key}`,
            lane: "nearby",
            scope: `prefetch-preview:${instanceId}:${axisToUse}`,
            priority: 30,
            exec: (signal) =>
              fetchPreviewPayload({
                sessionId,
                instanceId,
                axis: axisToUse,
                zIndex: neighbor,
                includeAll,
                includeActive,
                imageOnly,
                maxDim,
                signal,
              }),
          })
          .then((payload) => {
            cachePreview(key, payload);
          })
          .catch(() => {});
      }),
    );
  };

  const loadInstancePreview = async (
    instanceId,
    zIndex,
    axisOverride,
    options = {},
  ) => {
    const sessionToUse = sessionId;
    if (!sessionToUse || !instanceId) return;
    const axisToUse = axisOverride ?? viewAxis;
    const maxDim = parsePositiveInt(options.maxDim, PREVIEW_MAX_DIM);
    const qualityLabel = options.qualityLabel || `preview-${maxDim}`;
    const imageOnly = options.imageOnly === true;
    const includeAllContext = options.includeAllContext !== false;
    const shouldPrefetch =
      options.prefetchNeighbors !== false && !isFastScrubRef.current;
    const prefetchDistance =
      options.prefetchDistance ??
      (isFastScrubRef.current ? 0 : PREVIEW_PREFETCH_RADIUS);
    const priority = Number.isFinite(options.priority) ? options.priority : 120;
    const includeAll =
      !imageOnly &&
      includeAllContext &&
      supportsAllInstanceOverlay(instanceMode) &&
      overlayAllAlpha > 0.001;
    const includeActive = !imageOnly && overlayActiveAlpha > 0.001;
    const cacheKey = buildCacheKey({
      instanceId,
      axis: axisToUse,
      zIndex,
      includeAll,
      includeActive,
      quality: qualityLabel,
    });
    const cached = previewCache.current.get(cacheKey);
    if (cached) {
      perfCount("preview-cache-hit");
      logProofreadingEvent(
        "proofreading_slice_preview_cache_hit",
        {
          instanceId,
          zIndex,
          axis: axisToUse,
          quality: qualityLabel,
          imageOnly,
        },
        { throttleMs: 500 },
      );
      setPreviewView(cached);
      setSliderZ(cached.zIndex ?? zIndex);
      setAxisTotal(cached.total ?? axisTotal);
      return;
    }

    const lane = `preview:${instanceId}:${axisToUse}`;
    const requestKey = `${lane}:${cacheKey}`;
    const startedAt = performance.now();
    try {
      perfCount("request_start");
      logProofreadingEvent(
        "proofreading_slice_preview_requested",
        {
          instanceId,
          zIndex,
          axis: axisToUse,
          quality: qualityLabel,
          imageOnly,
          maxDim,
        },
        { throttleMs: 250 },
      );
      const previewPayload = await schedulerRef.current.run({
        key: requestKey,
        lane: "interactive",
        scope: `preview:${instanceId}:${axisToUse}`,
        priority,
        exec: (signal) =>
          fetchPreviewPayload({
            sessionId: sessionToUse,
            instanceId,
            axis: axisToUse,
            zIndex,
            includeAll,
            includeActive,
            imageOnly,
            maxDim,
            signal,
          }),
      });
      if (!isScrubbingRef.current) return;
      cachePreview(cacheKey, previewPayload);
      setPreviewView(previewPayload);
      setSliderZ(previewPayload.zIndex);
      setAxisTotal(previewPayload.total);
      perfLog("first_preview_paint", startedAt);
      logProofreadingEvent(
        "proofreading_slice_preview_loaded",
        {
          instanceId,
          zIndex: previewPayload.zIndex,
          axis: axisToUse,
          quality: qualityLabel,
          imageOnly,
          elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
        },
        { throttleMs: 250 },
      );
      if (shouldPrefetch && prefetchDistance > 0) {
        prefetchPreviewNeighbors(
          instanceId,
          previewPayload.zIndex,
          axisToUse,
          includeAll,
          includeActive,
          maxDim,
          qualityLabel,
          prefetchDistance,
          imageOnly,
        );
      }
    } catch (error) {
      if (isAbortError(error)) {
        perfCount("dropped_request");
      } else {
        console.warn("Preview load failed:", error);
      }
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
    if (!sessionToUse || !instanceId) return;
    const axisToUse = axisOverride ?? viewAxis;
    const includeAll =
      supportsAllInstanceOverlay(modeOverride ?? instanceMode) &&
      overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
    const requestIdentity = [
      instanceId,
      axisToUse,
      zIndex,
      includeAll ? "all" : "noall",
      includeActive ? "active" : "noactive",
      includeRaw ? "raw" : "noraw",
    ].join(":");
    if (fullRequestInFlightRef.current === requestIdentity) {
      return;
    }
    const cacheKey = buildCacheKey({
      instanceId,
      axis: axisToUse,
      zIndex,
      includeAll,
      includeActive,
      quality: "full",
    });
    const cached = viewCache.current.get(cacheKey);
    if (cached && (!includeRaw || cached.maskRawBase64)) {
      perfCount("full-cache-hit");
      logProofreadingEvent("proofreading_slice_full_cache_hit", {
        instanceId,
        zIndex,
        axis: axisToUse,
        includeRaw,
      });
      lastFullRequestKeyRef.current = requestIdentity;
      setViewState(cached);
      setAxisTotal(cached.total ?? axisTotal);
      setSliderZ(cached.zIndex);
      return;
    }
    if (cached && includeRaw && !cached.maskRawBase64) {
      try {
        const rawPayload = await fetchInstanceBundle({
          sessionId: sessionToUse,
          instanceId,
          axis: axisToUse,
          zIndex: cached.zIndex,
          kinds: ["mask_active_binary"],
          maxDim: null,
          quality: "full",
        });
        const merged = { ...cached, maskRawBase64: rawPayload.maskRawBase64 };
        cacheView(cacheKey, merged);
        lastFullRequestKeyRef.current = requestIdentity;
        setViewState(merged);
        setAxisTotal(merged.total ?? axisTotal);
        setSliderZ(merged.zIndex);
        return;
      } catch (error) {
        if (!isAbortError(error)) {
          console.warn(
            "Raw mask fetch failed, falling back to full fetch:",
            error,
          );
        }
      }
    }

    setLoadingView(true);
    fullRequestInFlightRef.current = requestIdentity;
    const lane = `full:${instanceId}:${axisToUse}`;
    const requestKey = `${lane}:${cacheKey}`;
    const startedAt = performance.now();
    try {
      perfCount("request_start");
      logProofreadingEvent("proofreading_slice_full_requested", {
        instanceId,
        zIndex,
        axis: axisToUse,
        includeRaw,
        includeAll,
        includeActive,
      });
      const fullPayload = await schedulerRef.current.run({
        key: requestKey,
        lane: "interactive",
        scope: `full:${instanceId}:${axisToUse}`,
        priority: 100,
        exec: async (signal) => {
          const kinds = ["image"];
          if (includeActive) kinds.push("mask_active");
          if (includeAll) kinds.push("mask_all");
          if (includeRaw) kinds.push("mask_active_binary");
          const payload = await fetchInstanceBundle({
            sessionId: sessionToUse,
            instanceId,
            axis: axisToUse,
            zIndex,
            kinds,
            maxDim: null,
            quality: "full",
            signal,
          });
          return payload;
        },
      });

      cacheView(cacheKey, fullPayload);
      lastFullRequestKeyRef.current = requestIdentity;
      setViewState(fullPayload);
      setAxisTotal(fullPayload.total);
      setSliderZ(fullPayload.zIndex);
      perfLog("full_paint", startedAt);
      logProofreadingEvent("proofreading_slice_full_loaded", {
        instanceId,
        zIndex: fullPayload.zIndex,
        axis: axisToUse,
        includeRaw,
        elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
      });
      prefetchAdjacent(
        instanceId,
        fullPayload.zIndex,
        sessionToUse,
        axisToUse,
        fullPayload.total,
        includeAll,
        includeActive,
        includeRaw,
      );
    } catch (error) {
      if (isAbortError(error)) {
        perfCount("dropped_request");
      } else {
        console.error("Failed to load instance view:", error);
        logProofreadingEvent(
          "proofreading_slice_full_failed",
          {
            instanceId,
            zIndex,
            axis: axisToUse,
            error: getErrorMessage(error, "Failed to load instance view"),
          },
          { level: "ERROR" },
        );
        message.error(getErrorMessage(error, "Failed to load instance view"));
      }
    } finally {
      if (fullRequestInFlightRef.current === requestIdentity) {
        fullRequestInFlightRef.current = null;
      }
      setLoadingView(false);
    }
  };

  const clearScrubTimers = () => {
    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
      previewDebounceRef.current = null;
    }
    if (scrubIdleRef.current) {
      clearTimeout(scrubIdleRef.current);
      scrubIdleRef.current = null;
    }
  };

  const clearSliceWheelTimers = () => {
    Object.values(sliceWheelRef.current || {}).forEach((state) => {
      if (state?.commitTimer) {
        clearTimeout(state.commitTimer);
      }
    });
    sliceWheelRef.current = {};
  };

  const selectInstance = (instance) => {
    clearScrubTimers();
    clearSliceWheelTimers();
    isScrubbingRef.current = false;
    isFastScrubRef.current = false;
    const axisIndex = clampSliceIndex(
      getAxisIndexForInstance(instance, viewAxis),
      axisTotal || totalLayers,
    );
    setActiveInstanceId(instance.id);
    setActiveInstance(instance);
    setViewState((prev) => ({
      ...prev,
      zIndex: axisIndex,
      instanceId: instance.id,
      imageBase64: null,
      maskAllBase64: null,
      maskActiveBase64: null,
      maskRawBase64: null,
    }));
    setSliderZ(axisIndex);
    setCommittedZ(axisIndex);
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

  const handleSliceChange = (value) => {
    const nextIndex = clampSliceIndex(value, axisTotal || totalLayers);
    const now =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    const previous = scrubTrackRef.current;
    const dt = Math.max(now - (previous?.at || 0), 1);
    const delta = Math.abs(nextIndex - (previous?.zIndex ?? nextIndex));
    const slicesPerSec = (delta * 1000) / dt;
    isFastScrubRef.current = slicesPerSec >= FAST_SCRUB_SLICES_PER_SEC;
    scrubTrackRef.current = { zIndex: nextIndex, at: now };

    setSliderZ(nextIndex);
    isScrubbingRef.current = true;
    if (!activeInstanceId || !sessionId) return;

    const axisToUse = viewAxis;
    const fullIncludeAll =
      supportsAllInstanceOverlay(instanceMode) && overlayAllAlpha > 0.001;
    const fullIncludeActive = overlayActiveAlpha > 0.001;
    const includeAll = false;
    const includeActive = false;
    const fullKey = buildCacheKey({
      instanceId: activeInstanceId,
      axis: axisToUse,
      zIndex: nextIndex,
      includeAll: fullIncludeAll,
      includeActive: fullIncludeActive,
      quality: "full",
    });
    const fullCached = viewCache.current.get(fullKey);
    if (fullCached) {
      setViewState(fullCached);
      setAxisTotal(fullCached.total);
      return;
    }

    const previewKey = buildCacheKey({
      instanceId: activeInstanceId,
      axis: axisToUse,
      zIndex: nextIndex,
      includeAll,
      includeActive,
      quality: `preview-${PREVIEW_MAX_DIM}`,
    });
    const thumbKey = buildCacheKey({
      instanceId: activeInstanceId,
      axis: axisToUse,
      zIndex: nextIndex,
      includeAll,
      includeActive,
      quality: `thumb-${THUMB_MAX_DIM}`,
    });
    const previewCached = previewCache.current.get(previewKey);
    const thumbCached = previewCache.current.get(thumbKey);
    if (previewCached) {
      setPreviewView(previewCached);
      setAxisTotal(previewCached.total ?? axisTotal);
      return;
    }
    if (thumbCached) {
      setPreviewView(thumbCached);
      setAxisTotal(thumbCached.total ?? axisTotal);
    } else {
      loadInstancePreview(activeInstanceId, nextIndex, axisToUse, {
        maxDim: THUMB_MAX_DIM,
        qualityLabel: `thumb-${THUMB_MAX_DIM}`,
        prefetchNeighbors: false,
        imageOnly: true,
        priority: 160,
      });
    }

    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
    }
    if (scrubIdleRef.current) {
      clearTimeout(scrubIdleRef.current);
    }
    previewDebounceRef.current = setTimeout(
      () => {
        loadInstancePreview(activeInstanceId, nextIndex, axisToUse, {
          maxDim: PREVIEW_MAX_DIM,
          qualityLabel: `preview-${PREVIEW_MAX_DIM}`,
          prefetchNeighbors: !isFastScrubRef.current,
          prefetchDistance: isFastScrubRef.current ? 0 : 1,
          imageOnly: true,
          priority: 120,
        });
      },
      isFastScrubRef.current ? 100 : 60,
    );

    scrubIdleRef.current = setTimeout(() => {
      if (!isScrubbingRef.current) return;
      loadInstancePreview(activeInstanceId, nextIndex, axisToUse, {
        maxDim: PREVIEW_MAX_DIM,
        qualityLabel: `preview-rich-${PREVIEW_MAX_DIM}`,
        prefetchNeighbors: !isFastScrubRef.current,
        prefetchDistance: isFastScrubRef.current ? 0 : 1,
        imageOnly: false,
        includeAllContext: false,
        priority: 110,
      });
    }, SCRUB_IDLE_MS);
  };

  const handleSliceCommit = (value) => {
    if (!activeInstanceId) return;
    const nextIndex = clampSliceIndex(value, axisTotal || totalLayers);
    setSliderZ(nextIndex);
    setCommittedZ(nextIndex);
    clearScrubTimers();
    isScrubbingRef.current = false;
    isFastScrubRef.current = false;
    scrubTrackRef.current = {
      zIndex: nextIndex,
      at: typeof performance !== "undefined" ? performance.now() : Date.now(),
    };
    logProofreadingEvent("proofreading_slice_committed", {
      zIndex: nextIndex,
      axis: viewAxis,
    });
    loadInstanceView(activeInstanceId, nextIndex, true, undefined, viewAxis);
  };

  const handleAxisChange = (nextAxis) => {
    clearScrubTimers();
    clearSliceWheelTimers();
    const axisValue = nextAxis || "xy";
    isScrubbingRef.current = false;
    isFastScrubRef.current = false;
    setViewAxis(axisValue);
    const cachedPlane = orthoviewPayloadsRef.current?.[axisValue];
    const cachedTotal = Number(cachedPlane?.total) || 0;
    const axisIndex = Number.isFinite(Number(cachedPlane?.zIndex))
      ? Number(cachedPlane.zIndex)
      : Math.max(
          0,
          Math.round(Number(getAxisIndexForInstance(activeInstance, axisValue)) || 0),
        );
    if (cachedTotal) {
      setAxisTotal(cachedTotal);
    }
    setViewState((prev) => ({
      ...prev,
      ...(cachedPlane || {}),
      zIndex: axisIndex,
      axis: axisValue,
      imageBase64: cachedPlane?.imageBase64 || null,
      maskAllBase64: cachedPlane?.maskAllBase64 || null,
      maskActiveBase64: cachedPlane?.maskActiveBase64 || null,
      maskRawBase64: cachedPlane?.maskRawBase64 || null,
      total: cachedTotal || prev.total,
      instanceId: activeInstanceId,
    }));
    setSliderZ(axisIndex);
    setCommittedZ(axisIndex);
  };

  const reloadOrthoviewAxis = async (axis, zIndex) => {
    if (!sessionId || !activeInstanceId || axis === viewAxis) return;
    const includeAll =
      supportsAllInstanceOverlay(instanceMode) && overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
    const kinds = ["image", "mask_active_binary"];
    if (includeActive) kinds.push("mask_active");
    if (includeAll) kinds.push("mask_all");
    setLoadingOrthoviews(true);
    try {
      const payload = await fetchInstanceBundle({
        sessionId,
        instanceId: activeInstanceId,
        axis,
        zIndex,
        kinds,
        maxDim: null,
        quality: "full",
      });
      setOrthoviewPayloads((prev) => {
        if (prev[axis]) revokePayloadUrls(prev[axis]);
        const next = { ...prev, [axis]: payload };
        orthoviewPayloadsRef.current = next;
        return next;
      });
    } catch (error) {
      if (!isAbortError(error)) {
        console.warn("Failed to reload orthogonal editable plane:", error);
      }
    } finally {
      setLoadingOrthoviews(false);
    }
  };

  const handleSaveMaskForAxis = async (axis, zIndex, planeState, maskBase64) => {
    if (!sessionId || !activeInstanceId) return;
    const targetIndex = clampSliceIndex(
      zIndex,
      axisTotal || totalLayers,
    );
    const rawMaskMatchesCurrentSlice =
      planeState?.axis === axis &&
      planeState?.zIndex === targetIndex &&
      planeState?.instanceId === activeInstanceId &&
      Boolean(planeState?.maskRawBase64);
    if (!rawMaskMatchesCurrentSlice) {
      logProofreadingEvent(
        "proofreading_mask_save_blocked_stale_mask",
        {
          targetIndex,
          viewStateIndex: planeState?.zIndex,
          viewStateAxis: planeState?.axis,
          viewStateInstanceId: planeState?.instanceId,
          hasRawMask: Boolean(planeState?.maskRawBase64),
        },
        { level: "WARNING" },
      );
      message.warning("Wait for the editable mask for this slice to load.");
      if (axis === viewAxis) {
        loadInstanceView(
          activeInstanceId,
          targetIndex,
          true,
          undefined,
          viewAxis,
        );
      } else {
        reloadOrthoviewAxis(axis, targetIndex);
      }
      throw new Error("Editable mask is not loaded for the current slice");
    }
    setSavingMask(true);
    try {
      logProofreadingEvent("proofreading_mask_save_started", {
        instanceId: activeInstanceId,
        axis,
        zIndex: targetIndex,
      });
      const response = await apiClient.post("/eh/detection/instance-mask", {
        session_id: sessionId,
        instance_id: activeInstanceId,
        axis,
        z_index: targetIndex,
        mask_base64: maskBase64,
        ui_state: {
          axis,
          overlay_all_alpha: overlayAllAlpha,
          overlay_active_alpha: overlayActiveAlpha,
          last_instance_id: activeInstanceId,
          last_slice_index: targetIndex,
        },
      });
      clearFrameCaches();
      if (response.data?.persistence) {
        setPersistence(response.data.persistence);
      }
      setMeshRevision((revision) => revision + 1);
      message.success("Instance mask updated");
      logProofreadingEvent("proofreading_mask_save_completed", {
        instanceId: activeInstanceId,
        axis,
        zIndex: targetIndex,
        pixelsChanged: response.data?.edit?.pixels_changed,
        artifactPath: response.data?.persistence?.artifact_path,
        artifactExists: response.data?.persistence?.artifact_exists,
      });
      refreshPersistenceStatus();
      if (axis === viewAxis) {
        loadInstanceView(
          activeInstanceId,
          targetIndex,
          true,
          undefined,
          viewAxis,
        );
      } else {
        reloadOrthoviewAxis(axis, targetIndex);
      }
    } catch (error) {
      console.error("Failed to save mask:", error);
      logProofreadingEvent(
        "proofreading_mask_save_failed",
        {
          instanceId: activeInstanceId,
          axis,
          zIndex: targetIndex,
          error: getErrorMessage(error, "Failed to save mask"),
        },
        { level: "ERROR" },
      );
      message.error(getErrorMessage(error, "Failed to save mask"));
      throw error;
    } finally {
      setSavingMask(false);
    }
  };

  const handleStageForRetraining = async () => {
    const correctedMaskPath =
      persistence?.artifact_path ||
      persistence?.last_export_path ||
      activeWorkflow?.corrected_mask_path ||
      activeWorkflow?.mask_path ||
      activeWorkflow?.label_path;
    if (!correctedMaskPath) {
      message.warning("No edited mask artifact is available yet.");
      return;
    }
    if (!workflowContext?.workflow?.id) {
      message.warning("Workflow state is not available yet.");
      return;
    }

    try {
      await workflowContext.updateWorkflow({
        stage: "retraining_staged",
        corrected_mask_path: correctedMaskPath,
      });
      await workflowContext.appendEvent({
        actor: "user",
        event_type: "retraining.staged",
        stage: "retraining_staged",
        summary: "Staged corrected masks for retraining.",
        payload: {
          corrected_mask_path: correctedMaskPath,
          ehtool_session_id: sessionId,
          source: "proofreading_persistence",
        },
      });
      if (appContext?.trainingState?.setInputLabel) {
        appContext.trainingState.setInputLabel(correctedMaskPath);
      }
      message.success("Corrected masks staged for retraining.");
    } catch (error) {
      message.error(
        getErrorMessage(
          error,
          "Failed to stage corrected masks for retraining",
        ),
      );
    }
  };

  const resetProofreadingSession = () => {
    clearFrameCaches();
    setSessionId(null);
    setActiveInstanceId(null);
    setActiveInstance(null);
    setInstances([]);
    setPersistence(null);
    setVolumePreview(null);
    setLiveMaskDraft(null);
    setOrthoviewPayloads((prev) => {
      Object.values(prev).forEach((payload) => revokePayloadUrls(payload));
      orthoviewPayloadsRef.current = {};
      return {};
    });
  };

  const formatCount = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toLocaleString() : value || 0;
  };

  const currentAxisTotal = axisTotal || totalLayers;
  const currentSliceIndex = clampSliceIndex(
    sliderZ ?? viewState.zIndex,
    currentAxisTotal,
  );
  const isEditableMaskReady =
    Boolean(viewState.maskRawBase64) &&
    viewState.axis === viewAxis &&
    viewState.zIndex === currentSliceIndex &&
    viewState.instanceId === activeInstanceId;

  useEffect(() => {
    if (
      !sessionId ||
      !activeInstanceId ||
      !activeInstance ||
      instanceMode === "none"
    ) {
      setLoadingOrthoviews(false);
      setOrthoviewPayloads((prev) => {
        Object.values(prev).forEach((payload) => revokePayloadUrls(payload));
        orthoviewPayloadsRef.current = {};
        return {};
      });
      return undefined;
    }

    let cancelled = false;
    const controller = new AbortController();
    const axesToLoad = ORTHO_PANES.filter((pane) => pane.axis !== viewAxis);
    const includeAll =
      supportsAllInstanceOverlay(instanceMode) && overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
    const kinds = ["image", "mask_active_binary"];
    if (includeActive) kinds.push("mask_active");
    if (includeAll) kinds.push("mask_all");

    setLoadingOrthoviews(true);
    Promise.allSettled(
      axesToLoad.map(async (pane) => {
        const zIndex = Math.max(
          0,
          Math.round(Number(getAxisIndexForInstance(activeInstance, pane.axis)) || 0),
        );
        const payload = await fetchInstanceBundle({
          sessionId,
          instanceId: activeInstanceId,
          axis: pane.axis,
          zIndex,
          kinds,
          maxDim: null,
          quality: "full",
          signal: controller.signal,
        });
        return { axis: pane.axis, payload };
      }),
    )
      .then((results) => {
        const next = {};
        results.forEach((result) => {
          if (result.status !== "fulfilled") return;
          next[result.value.axis] = result.value.payload;
        });
        if (cancelled) {
          Object.values(next).forEach((payload) => revokePayloadUrls(payload));
          return;
        }
        setOrthoviewPayloads((prev) => {
          Object.values(prev).forEach((payload) => revokePayloadUrls(payload));
          orthoviewPayloadsRef.current = next;
          return next;
        });
      })
      .catch((error) => {
        if (!isAbortError(error)) {
          console.warn("Failed to load orthogonal previews:", error);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingOrthoviews(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // fetchInstanceBundle is recreated each render; the request is keyed by the
    // explicit session, instance, axis, and overlay state above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeInstance,
    activeInstanceId,
    currentAxisTotal,
    instanceMode,
    meshRevision,
    overlayActiveAlpha,
    overlayAllAlpha,
    sessionId,
    totalLayers,
    viewAxis,
  ]);

  if (!sessionId) {
    return (
      <div style={{ padding: "24px 0" }}>
        <DatasetLoader
          onLoad={handleDatasetLoad}
          loading={loadingInstances}
          workflow={activeWorkflow}
        />
      </div>
    );
  }

  const compactWorkbench = windowWidth < 980;
  const queuePanelVisible = showQueue && !compactWorkbench;
  const compactQueueVisible = showQueue && compactWorkbench;
  const persistenceColor = persistence?.last_error
    ? "red"
    : persistence?.artifact_exists
      ? "green"
      : persistence?.enabled
        ? "blue"
        : "default";
  const persistenceLabel = persistence?.last_error
    ? "Save issue"
    : persistence?.artifact_exists
      ? "Edits saved"
      : persistence?.enabled
        ? "Ready to save"
        : "No persistence";

  const activeInstanceMeta =
    activeInstance && instanceMode !== "none" ? (
      <Tag color="cyan" style={{ margin: 0 }}>
        Instance #{activeInstance.id}
      </Tag>
    ) : (
      <Text type="secondary" style={{ fontSize: 12 }}>
        Select an instance.
      </Text>
    );

  const progressPanel = (
    <div style={{ display: "grid", gap: 4 }}>
      <Text strong style={{ fontSize: 13 }}>
        {instances.length} instances
      </Text>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {activeInstance
          ? `Selected #${activeInstance.id}`
          : "Select an instance to inspect."}
      </Text>
    </div>
  );

  const queuePanel = (
    <Card
      size="small"
      title="Review queue"
      extra={
        <Tag color="blue" style={{ margin: 0 }}>
          {instances.length} total
        </Tag>
      }
      bodyStyle={{ display: "grid", gap: 12 }}
      style={{ height: "100%", borderRadius: 14 }}
    >
      {progressPanel}
      <Divider style={{ margin: "4px 0" }} />
        <InstanceNavigator
          instances={instances}
          activeInstanceId={activeInstanceId}
          onSelect={selectInstance}
          filterText={filterText}
          onFilterText={setFilterText}
          showClassification={false}
        />
      </Card>
  );

  const activeInstanceCoordinates = activeInstance
    ? `XYZ ${formatCount(activeInstance.com_x)}, ${formatCount(
        activeInstance.com_y,
      )}, ${formatCount(activeInstance.com_z)}`
    : "XYZ --";

  const viewerToolbar = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        flexWrap: "wrap",
        padding: "12px 16px",
        borderBottom: "1px solid #e5e7eb",
        background: "#ffffff",
      }}
    >
      <Space size="small" wrap>
        <Text strong style={{ fontSize: 13 }}>
          {formatAxisLabel(viewAxis)} {currentSliceIndex + 1} /{" "}
          {Math.max(currentAxisTotal, 1)}
        </Text>
        <div style={{ width: 220, maxWidth: "42vw" }}>
          <Slider
            min={0}
            max={Math.max(currentAxisTotal - 1, 0)}
            value={currentSliceIndex}
            disabled={currentAxisTotal <= 1}
            tooltip={{ formatter: (value) => `Slice ${Number(value) + 1}` }}
            onChange={handleSliceChange}
            onChangeComplete={handleSliceCommit}
          />
        </div>
        <Tag color="default" style={{ margin: 0 }}>
          {activeInstanceCoordinates}
        </Tag>
        {activeInstanceMeta}
        {!isEditableMaskReady && (
          <Tag color="blue" style={{ margin: 0 }}>
            loading mask
          </Tag>
        )}
        {savingMask && (
          <Tag color="processing" style={{ margin: 0 }}>
            saving
          </Tag>
        )}
      </Space>
      <Space size="small" wrap>
        <Button size="small" onClick={goToNextInstance}>
          Next instance
        </Button>
        <Button size="small" type="primary" onClick={handleStageForRetraining}>
          Use edits for training
        </Button>
      </Space>
    </div>
  );

  const getActiveEditor = () => editorRefs.current[viewAxis] || null;
  const setActiveTool = (nextTool) => {
    getActiveEditor()?.setTool?.(nextTool);
    setActiveToolState((prev) => ({ ...prev, tool: nextTool }));
  };
  const setActiveBrushSize = (value) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return;
    const nextSize = Math.max(1, Math.min(50, Math.round(numeric)));
    getActiveEditor()?.setBrushSize?.(nextSize);
    setActiveToolState((prev) => ({ ...prev, activeBrushSize: nextSize }));
  };
  const brushSizeControl = (
    <div style={{ width: 220, padding: "2px 4px" }}>
      <Text strong style={{ display: "block", marginBottom: 8 }}>
        Brush size
      </Text>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 64px",
          gap: 10,
          alignItems: "center",
        }}
      >
        <Slider
          min={1}
          max={50}
          value={activeToolState.activeBrushSize || 10}
          onChange={setActiveBrushSize}
          tooltip={{ formatter: (value) => `${value}px` }}
        />
        <InputNumber
          min={1}
          max={50}
          size="small"
          value={activeToolState.activeBrushSize || 10}
          onChange={setActiveBrushSize}
        />
      </div>
    </div>
  );
  const normalizeWheelDelta = (wheel) => {
    const deltaY = Number(wheel?.deltaY ?? wheel ?? 0);
    const deltaMode = Number(wheel?.deltaMode ?? 0);
    if (deltaMode === 1) return deltaY * 32;
    if (deltaMode === 2) return deltaY * 240;
    return deltaY;
  };

  const stepAxisSlice = (
    axis,
    currentIndex,
    delta,
    totalOverride,
    options = {},
  ) => {
    const totalForPlane =
      Number(totalOverride) ||
      (axis === viewAxis ? currentAxisTotal : 0) ||
      currentAxisTotal ||
      totalLayers;
    const nextIndex = clampSliceIndex(
      currentIndex + delta,
      totalForPlane,
    );
    if (nextIndex === currentIndex) return nextIndex;
    if (axis === viewAxis) {
      if (options.previewOnly) {
        handleSliceChange(nextIndex);
      } else {
        handleSliceCommit(nextIndex);
      }
    } else {
      reloadOrthoviewAxis(axis, nextIndex);
    }
    return nextIndex;
  };
  const handlePaneSliceWheel = (axis, currentIndex, wheel, totalOverride) => {
    const deltaPixels = normalizeWheelDelta(wheel);
    if (Math.abs(deltaPixels) < 1) return;
    const now =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    const state = sliceWheelRef.current[axis] || {};
    const baseIndex =
      now - (state.at || 0) > 320
        ? currentIndex
        : Number.isFinite(state.index)
          ? state.index
          : currentIndex;
    const nextRemainder =
      (now - (state.at || 0) > 320 ? 0 : state.remainder || 0) + deltaPixels;
    let steps = Math.trunc(nextRemainder / WHEEL_SLICE_DELTA_PX);
    if (!steps) {
      sliceWheelRef.current[axis] = {
        ...state,
        index: baseIndex,
        remainder: nextRemainder,
        at: now,
      };
      return;
    }
    steps = Math.max(-4, Math.min(4, steps));
    const usedDelta = steps * WHEEL_SLICE_DELTA_PX;
    const nextIndex = stepAxisSlice(axis, baseIndex, steps, totalOverride, {
      previewOnly: axis === viewAxis,
    });
    if (state.commitTimer) {
      clearTimeout(state.commitTimer);
    }
    const nextState = {
      index: nextIndex,
      remainder: nextRemainder - usedDelta,
      at: now,
      commitTimer: null,
    };
    if (axis === viewAxis) {
      nextState.commitTimer = setTimeout(() => {
        handleSliceCommit(nextIndex);
        if (sliceWheelRef.current[axis]) {
          sliceWheelRef.current[axis].remainder = 0;
          sliceWheelRef.current[axis].commitTimer = null;
        }
      }, WHEEL_SLICE_IDLE_MS);
    }
    sliceWheelRef.current[axis] = nextState;
  };
  const toolButtonStyle = {
    width: 36,
    height: 36,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  };
  const sharedToolRail = (
    <aside
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        padding: "8px 6px",
        borderRight: "1px solid #1f2937",
        background: "#0b1220",
      }}
    >
      <Tag color="blue" style={{ margin: 0, fontSize: 10 }}>
        {formatAxisLabel(viewAxis)}
      </Tag>
      <div
        style={{
          width: 28,
          height: 1,
          background: "rgba(148, 163, 184, 0.28)",
          margin: "2px 0",
        }}
      />
      <Tooltip title="Paint">
        <Button
          size="small"
          type={activeToolState.tool === "paint" ? "primary" : "default"}
          icon={<EditOutlined />}
          disabled={!activeToolState.canEdit}
          onClick={() => setActiveTool("paint")}
          style={toolButtonStyle}
        />
      </Tooltip>
      <Tooltip title="Erase">
        <Button
          size="small"
          type={activeToolState.tool === "erase" ? "primary" : "default"}
          icon={<ClearOutlined />}
          disabled={!activeToolState.canEdit}
          onClick={() => setActiveTool("erase")}
          style={toolButtonStyle}
        />
      </Tooltip>
      <Popover
        content={brushSizeControl}
        trigger="click"
        placement="right"
        overlayStyle={{ width: 252 }}
      >
        <Tooltip title="Brush size">
          <Button
            size="small"
            disabled={!activeToolState.canEdit}
            style={{
              ...toolButtonStyle,
              fontSize: 11,
              fontWeight: 700,
              padding: 0,
            }}
          >
            {activeToolState.activeBrushSize || 10}
          </Button>
        </Tooltip>
      </Popover>
      <Tooltip title="Pan">
        <Button
          size="small"
          type={activeToolState.tool === "hand" ? "primary" : "default"}
          icon={<DragOutlined />}
          onClick={() => setActiveTool("hand")}
          style={toolButtonStyle}
        />
      </Tooltip>
      <Tooltip title={activeToolState.showMask ? "Hide mask" : "Show mask"}>
        <Button
          size="small"
          icon={
            activeToolState.showMask ? (
              <EyeInvisibleOutlined />
            ) : (
              <EyeOutlined />
            )
          }
          onClick={() => getActiveEditor()?.toggleMask?.()}
          style={toolButtonStyle}
        />
      </Tooltip>
      <Tooltip title="Save active plane">
        <Button
          size="small"
          type={activeToolState.hasUnsavedEdits ? "primary" : "default"}
          icon={<SaveOutlined />}
          disabled={!activeToolState.canEdit}
          onClick={() => getActiveEditor()?.save?.()}
          style={toolButtonStyle}
        />
      </Tooltip>
      <div
        style={{
          width: 28,
          height: 1,
          background: "rgba(148, 163, 184, 0.28)",
          margin: "2px 0",
        }}
      />
      <Tooltip title="Zoom in">
        <Button
          size="small"
          icon={<ZoomInOutlined />}
          onClick={() => getActiveEditor()?.zoomIn?.()}
          style={toolButtonStyle}
        />
      </Tooltip>
      <Tooltip title="Zoom out">
        <Button
          size="small"
          icon={<ZoomOutOutlined />}
          onClick={() => getActiveEditor()?.zoomOut?.()}
          style={toolButtonStyle}
        />
      </Tooltip>
    </aside>
  );

  const editorSurface =
    loadingInstances && instances.length === 0 ? (
      <Card style={{ minHeight: 420, borderRadius: 14 }}>
        <div style={{ padding: 32, textAlign: "center" }}>
          <Title level={4}>Preparing instances...</Title>
          <Text type="secondary">
            Building the review queue and loading the first editable slice.
          </Text>
        </div>
      </Card>
    ) : instanceMode === "none" ? (
      <Card style={{ minHeight: 420, borderRadius: 14 }}>
        <div style={{ padding: 32, textAlign: "center" }}>
          <Title level={4}>Mask required</Title>
          <Text type="secondary">
            Load a dataset with a mask to enable instance proofreading.
          </Text>
        </div>
      </Card>
    ) : (
      <section
        data-proofreader-wheel-lock="true"
        style={{
          display: "grid",
          overflow: "hidden",
          borderRadius: 18,
          border: "1px solid #d8e1dc",
          background: "#ffffff",
          boxShadow: "0 18px 45px rgba(15, 23, 42, 0.08)",
        }}
      >
        {viewerToolbar}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "50px minmax(0, 1fr)",
            background: "#111827",
            minHeight: 0,
            overscrollBehavior: "contain",
          }}
        >
          {sharedToolRail}
          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                windowWidth < 1180
                  ? "minmax(0, 1fr)"
                  : "minmax(0, 1fr) minmax(0, 1fr)",
              gridAutoRows:
                windowWidth < 1180 ? "360px" : "minmax(260px, 1fr)",
              height:
                windowWidth < 1180
                  ? "auto"
                  : "clamp(560px, calc(100vh - 270px), 860px)",
              gap: 2,
              padding: 2,
              minWidth: 0,
              minHeight: 0,
              background: "#111827",
              overscrollBehavior: "contain",
            }}
          >
            {ORTHO_PANES.map((pane) => {
              const activePane = pane.axis === viewAxis;
              const payload = activePane
                ? viewState
                : orthoviewPayloads[pane.axis];
              const planeReady = Boolean(payload?.imageBase64);
              const planeIndex = clampSliceIndex(
                payload?.zIndex ??
                  getAxisIndexForInstance(activeInstance, pane.axis),
                payload?.total ||
                  (activePane ? currentAxisTotal : 0) ||
                  currentAxisTotal,
              );
              const planeTotal =
                Number(payload?.total) ||
                (activePane ? currentAxisTotal : 0) ||
                currentAxisTotal ||
                totalLayers;
              const planeCanEdit =
                Boolean(payload?.maskRawBase64) &&
                payload?.axis === pane.axis &&
                payload?.instanceId === activeInstanceId;
              return (
                <OrthoviewPane
                  key={pane.axis}
                  axis={pane.axis}
                  label={pane.label}
                  payload={payload}
                  loading={
                    activePane
                      ? loadingView || loadingInstances
                      : loadingOrthoviews
                  }
                  active={activePane}
                  editable={planeReady}
                  onActivate={() => {
                    if (!activePane) handleAxisChange(pane.axis);
                  }}
                  onSliceWheel={(wheel) =>
                    handlePaneSliceWheel(
                      pane.axis,
                      planeIndex,
                      wheel,
                      planeTotal,
                    )
                  }
                >
                  {planeReady && (
                    <ProofreadingEditor
                      ref={(node) => {
                        if (node) editorRefs.current[pane.axis] = node;
                        else delete editorRefs.current[pane.axis];
                      }}
                      imageBase64={payload.imageBase64}
                      maskBase64={payload.maskRawBase64}
                      overlayAllBase64={payload.maskAllBase64}
                      overlayActiveBase64={payload.maskActiveBase64}
                      overlayAllAlpha={overlayAllAlpha}
                      overlayActiveAlpha={overlayActiveAlpha}
                      loading={
                        activePane
                          ? loadingView || loadingInstances
                          : loadingOrthoviews
                      }
                      axis={pane.axis}
                      activeInstanceId={activeInstanceId}
                      onSave={(maskBase64) =>
                        handleSaveMaskForAxis(
                          pane.axis,
                          planeIndex,
                          payload,
                          maskBase64,
                        )
                      }
                      onMaskDraftChange={setLiveMaskDraft}
                      currentLayer={planeIndex}
                      totalLayers={planeTotal}
                      layerName={`${pane.label} ${planeIndex + 1}`}
                      canEdit={planeCanEdit}
                      saveDisabledReason="Editable mask for this slice is still loading."
                      minimalChrome
                      hideLayerToolbar
                      editorHeightOverride="100%"
                      keyboardEnabled={activePane}
                      hideToolPanel
                      onToolStateChange={
                        activePane ? setActiveToolState : undefined
                      }
                    />
                  )}
                </OrthoviewPane>
              );
            })}
            <Instance3DPreview
              preview={volumePreview}
              liveSlice={liveMaskDraft}
              axis={liveMaskDraft?.axis || viewAxis}
              layerIndex={liveMaskDraft?.layerIndex ?? currentSliceIndex}
              activeInstanceId={activeInstanceId}
              loading={loadingVolumePreview}
              fill
            />
          </div>
        </div>
      </section>
    );

  return (
    <Layout
      style={{
        minHeight: "calc(100vh - 180px)",
        background:
          "linear-gradient(135deg, rgba(240,247,244,0.95), rgba(245,241,232,0.95))",
        borderRadius: 18,
        padding: 12,
      }}
    >
      <Content style={{ padding: 0 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            padding: "4px 2px 14px",
          }}
        >
          <Space size="small" wrap>
            <Title level={4} style={{ margin: 0 }}>
              Mask proofreading
            </Title>
            <Tag color="geekblue" style={{ margin: 0 }}>
              {projectName || "Untitled project"}
            </Tag>
            <Tag color={persistenceColor} style={{ margin: 0 }}>
              {persistenceLabel}
            </Tag>
          </Space>
          <Space size="small" wrap>
            <Button size="small" onClick={resetProofreadingSession}>
              Change data
            </Button>
            <Button
              size="small"
              type={queuePanelVisible ? "default" : "primary"}
              onClick={() => setShowQueue((prev) => !prev)}
            >
              {queuePanelVisible ? "Focus view" : "Show queue"}
            </Button>
          </Space>
        </div>

        <Layout
          style={{
            background: "transparent",
            display: "flex",
            gap: 12,
          }}
        >
          {queuePanelVisible && (
            <Sider
              width={280}
              theme="light"
              style={{ background: "transparent" }}
            >
              {queuePanel}
            </Sider>
          )}
          <Content style={{ minWidth: 0 }}>{editorSurface}</Content>
        </Layout>

        {compactQueueVisible && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: 12,
              marginTop: 12,
            }}
          >
            {queuePanel}
          </div>
        )}
      </Content>
    </Layout>
  );
}

export default DetectionWorkflow;
