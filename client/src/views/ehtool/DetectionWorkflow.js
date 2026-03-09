import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Layout,
  message,
  Space,
  Typography,
  Button,
  Slider,
  Drawer,
  Collapse,
  Modal,
  Input,
  Dropdown,
  Tag,
} from "antd";
import { MoreOutlined } from "@ant-design/icons";
import DatasetLoader from "./DatasetLoader";
import ProgressTracker from "./ProgressTracker";
import InstanceNavigator from "./InstanceNavigator";
import ProofreadingEditor from "./ProofreadingEditor";
import SliceScheduler from "./SliceScheduler";
import { apiClient } from "../../api";

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
  6,
);
const ENABLE_FILMSTRIP_PREVIEW =
  process.env.REACT_APP_EH_ENABLE_FILMSTRIP_PREVIEW !== "false";

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
  const [committedZ, setCommittedZ] = useState(0);
  const previewDebounceRef = useRef(null);
  const previewCache = useRef(new Map());
  const previewCacheOrder = useRef([]);
  const previewCacheLimit = 180;
  const isScrubbingRef = useRef(false);
  const [overlayAllAlpha, setOverlayAllAlpha] = useState(0.08);
  const [overlayActiveAlpha, setOverlayActiveAlpha] = useState(0.8);
  const [savingMask, setSavingMask] = useState(false);
  const [classificationPending, setClassificationPending] = useState(false);
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1440,
  );
  const [showInstanceBrowser, setShowInstanceBrowser] = useState(false);
  const [showInspector, setShowInspector] = useState(true);
  const [inspectorSections, setInspectorSections] = useState([
    "review",
    "instances",
  ]);
  const [persistence, setPersistence] = useState(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportPath, setExportPath] = useState("");
  const [exportingMasks, setExportingMasks] = useState(false);
  const [overwritingSource, setOverwritingSource] = useState(false);
  const lastPersistenceErrorRef = useRef(null);

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

  const axisOptions = useMemo(
    () => [
      { label: "XY", value: "xy" },
      { label: "ZX", value: "zx" },
      { label: "ZY", value: "zy" },
    ],
    [],
  );

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
    const storedAll = Number(
      localStorage.getItem("mask-proofreading-overlay-all"),
    );
    const storedActive = Number(
      localStorage.getItem("mask-proofreading-overlay-active"),
    );
    const storedAxis = localStorage.getItem("mask-proofreading-axis");
    if (!Number.isNaN(storedAll)) {
      setOverlayAllAlpha(Math.min(Math.max(storedAll, 0), 1));
    }
    if (!Number.isNaN(storedActive)) {
      setOverlayActiveAlpha(Math.min(Math.max(storedActive, 0), 1));
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
    return () => {
      schedulerRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!sessionId || !activeInstanceId || instanceMode !== "instance") return;
    if (isScrubbingRef.current) return;
    const needsAll = overlayAllAlpha > 0.001 && !viewState.maskAllBase64;
    const needsActive =
      overlayActiveAlpha > 0.001 && !viewState.maskActiveBase64;
    if (needsAll || needsActive) {
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
    loadInstanceView(activeInstanceId, committedZ, true, undefined, viewAxis);
  }, [sessionId, activeInstanceId, viewAxis, committedZ]);

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
    const correct = instances.filter(
      (i) => i.classification === "correct",
    ).length;
    const incorrect = instances.filter(
      (i) => i.classification === "incorrect",
    ).length;
    const unsure = instances.filter(
      (i) => i.classification === "unsure",
    ).length;
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
    [
      payload.imageBase64,
      payload.maskAllBase64,
      payload.maskActiveBase64,
      payload.maskRawBase64,
    ]
      .filter((url) => typeof url === "string" && url.startsWith("blob:"))
      .forEach((url) => URL.revokeObjectURL(url));
  };

  const clearFrameCaches = () => {
    viewCache.current.forEach((cached) => revokePayloadUrls(cached));
    previewCache.current.forEach((cached) => revokePayloadUrls(cached));
    viewCache.current.clear();
    previewCache.current.clear();
    viewCacheOrder.current = [];
    previewCacheOrder.current = [];
  };

  useEffect(() => {
    return () => {
      clearFrameCaches();
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
      maskAllBase64: payload.maskAllBase64 ?? null,
      maskActiveBase64: payload.maskActiveBase64 ?? null,
      // Preview payloads do not carry editable raw masks; never retain stale raw
      // data from a previous slice.
      maskRawBase64: payload.maskRawBase64 ?? null,
      zIndex: payload.zIndex,
      axis: payload.axis,
      total: payload.total,
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
  }) => {
    if (!blob) return null;
    if (signal?.aborted) throw createAbortError();
    if (frameCount <= 1) return URL.createObjectURL(blob);

    const makeFrameUrl = (source, width, height, drawFrame) =>
      new Promise((resolve, reject) => {
        const frameHeight = Math.max(1, Math.floor(height / frameCount));
        const safeIndex = Math.max(0, Math.min(frameIndex, frameCount - 1));
        const sourceY = safeIndex * frameHeight;
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = frameHeight;
        const ctx = canvas.getContext("2d");
        drawFrame(ctx, sourceY, frameHeight);
        canvas.toBlob((frameBlob) => {
          if (!frameBlob) {
            reject(new Error("Failed to create filmstrip frame"));
            return;
          }
          resolve(URL.createObjectURL(frameBlob));
        }, blob.type || "image/png");
      });

    if (typeof createImageBitmap === "function") {
      const bitmap = await createImageBitmap(blob);
      try {
        if (signal?.aborted) throw createAbortError();
        return await makeFrameUrl(
          bitmap,
          bitmap.width,
          bitmap.height,
          (ctx, y, h) =>
            ctx.drawImage(bitmap, 0, y, bitmap.width, h, 0, 0, bitmap.width, h),
        );
      } finally {
        if (bitmap?.close) bitmap.close();
      }
    }

    const sourceUrl = URL.createObjectURL(blob);
    try {
      const image = await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () =>
          reject(new Error("Failed to decode filmstrip image"));
        img.src = sourceUrl;
      });
      if (signal?.aborted) throw createAbortError();
      return await makeFrameUrl(image, image.width, image.height, (ctx, y, h) =>
        ctx.drawImage(image, 0, y, image.width, h, 0, 0, image.width, h),
      );
    } finally {
      URL.revokeObjectURL(sourceUrl);
    }
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
    const batchStart =
      Math.floor(Math.max(zIndex, 0) / FILMSTRIP_BATCH_SIZE) *
      FILMSTRIP_BATCH_SIZE;
    const requests = kinds.map((kind) =>
      apiClient.get("/eh/detection/instance-filmstrip", {
        params: {
          session_id: sessionId,
          instance_id: instanceId,
          axis,
          z_start: batchStart,
          z_count: FILMSTRIP_BATCH_SIZE,
          kind,
          max_dim: maxDim || undefined,
          quality,
          format: kind === "image" ? "webp" : "png",
        },
        responseType: "blob",
        signal,
      }),
    );

    const responses = requests.length ? await Promise.all(requests) : [];
    const metaResponse = responses[0];
    const resolvedStart = Number(
      metaResponse?.headers?.["x-z-start"] ?? batchStart,
    );
    const resolvedCount = Number(
      metaResponse?.headers?.["x-z-count"] ?? FILMSTRIP_BATCH_SIZE,
    );
    const total = Number(
      metaResponse?.headers?.["x-total-layers"] ?? totalLayers ?? 0,
    );
    const resolvedAxis = metaResponse?.headers?.["x-axis"] ?? axis;
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
    };

    for (let idx = 0; idx < responses.length; idx += 1) {
      const kind = kinds[idx];
      const response = responses[idx];
      const frameUrl = await extractFilmstripFrameBlob({
        blob: response.data,
        frameIndex: frameOffset,
        frameCount: resolvedCount,
        signal,
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
    maxDim = PREVIEW_MAX_DIM,
    preferFilmstrip = ENABLE_FILMSTRIP_PREVIEW,
    signal,
  }) => {
    const kinds = ["image"];
    if (includeActive) kinds.push("mask_active");
    if (includeAll) kinds.push("mask_all");

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

      if (uiState && shouldRestore) {
        setOverlayAllAlpha(
          clampAlpha(uiState.overlay_all_alpha, overlayAllAlpha),
        );
        setOverlayActiveAlpha(
          clampAlpha(uiState.overlay_active_alpha, overlayActiveAlpha),
        );
      }

      setViewAxis(axisToUse);
      localStorage.setItem("mask-proofreading-axis", axisToUse);

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
        Math.max(zIndex - 2, 0),
        Math.max(zIndex - 1, 0),
        Math.min(zIndex + 1, totalForAxis - 1),
        Math.min(zIndex + 2, totalForAxis - 1),
      ]),
    );
    const kinds = ["image"];
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
    const shouldPrefetch = options.prefetchNeighbors !== false;
    const priority = Number.isFinite(options.priority) ? options.priority : 120;
    const includeAll = instanceMode === "instance" && overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
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
      if (shouldPrefetch) {
        prefetchPreviewNeighbors(
          instanceId,
          previewPayload.zIndex,
          axisToUse,
          includeAll,
          includeActive,
          maxDim,
          qualityLabel,
          PREVIEW_PREFETCH_RADIUS,
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
      (modeOverride ?? instanceMode) === "instance" && overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
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
    const lane = `full:${instanceId}:${axisToUse}`;
    const requestKey = `${lane}:${cacheKey}`;
    const startedAt = performance.now();
    try {
      perfCount("request_start");
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
      setViewState(fullPayload);
      setAxisTotal(fullPayload.total);
      setSliderZ(fullPayload.zIndex);
      perfLog("full_paint", startedAt);
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
        message.error(getErrorMessage(error, "Failed to load instance view"));
      }
    } finally {
      setLoadingView(false);
    }
  };

  const selectInstance = (instance) => {
    isScrubbingRef.current = false;
    const axisIndex = clampSliceIndex(
      getAxisIndexForInstance(instance, viewAxis),
      axisTotal || totalLayers,
    );
    setActiveInstanceId(instance.id);
    setActiveInstance(instance);
    setViewState((prev) => ({ ...prev, zIndex: axisIndex }));
    setSliderZ(axisIndex);
    setCommittedZ(axisIndex);
  };

  const goToNextUnreviewed = () => {
    if (instances.length === 0) return;
    const pool = instances.filter((inst) => inst.classification === "error");
    if (pool.length === 0) return;
    if (!activeInstanceId) {
      selectInstance(pool[0]);
      return;
    }
    const currentIdx = pool.findIndex((inst) => inst.id === activeInstanceId);
    const next = pool[(currentIdx + 1 + pool.length) % pool.length];
    if (next) selectInstance(next);
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
    if (classificationPending) return;

    const instanceId = activeInstanceId;
    const previousClassification =
      activeInstance?.classification ||
      instances.find((inst) => inst.id === instanceId)?.classification ||
      "error";

    const applyLocalClassification = (instanceToUpdate, nextClassification) => {
      setInstances((prev) =>
        prev.map((inst) =>
          inst.id === instanceToUpdate
            ? { ...inst, classification: nextClassification }
            : inst,
        ),
      );
      setActiveInstance((prev) =>
        prev && prev.id === instanceToUpdate
          ? { ...prev, classification: nextClassification }
          : prev,
      );
    };

    // Optimistic update to keep the interaction snappy.
    applyLocalClassification(instanceId, classification);
    setClassificationPending(true);

    try {
      await apiClient.post("/eh/detection/instance-classify", {
        session_id: sessionId,
        instance_ids: [instanceId],
        classification,
        ui_state: {
          axis: viewAxis,
          overlay_all_alpha: overlayAllAlpha,
          overlay_active_alpha: overlayActiveAlpha,
          last_instance_id: instanceId,
          last_slice_index: viewState.zIndex,
        },
      });
    } catch (error) {
      console.error("Failed to classify instance:", error);
      // Roll back local optimistic state if save fails.
      applyLocalClassification(instanceId, previousClassification);
      message.error(getErrorMessage(error, "Failed to classify instance"));
    } finally {
      setClassificationPending(false);
    }
  };

  const handleSliceChange = (value) => {
    const nextIndex = clampSliceIndex(value, axisTotal || totalLayers);
    setSliderZ(nextIndex);
    isScrubbingRef.current = true;
    if (!activeInstanceId || !sessionId) return;

    const axisToUse = viewAxis;
    const includeAll = instanceMode === "instance" && overlayAllAlpha > 0.001;
    const includeActive = overlayActiveAlpha > 0.001;
    const fullKey = buildCacheKey({
      instanceId: activeInstanceId,
      axis: axisToUse,
      zIndex: nextIndex,
      includeAll,
      includeActive,
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
        priority: 160,
      });
    }

    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
    }
    previewDebounceRef.current = setTimeout(() => {
      loadInstancePreview(activeInstanceId, nextIndex, axisToUse, {
        maxDim: PREVIEW_MAX_DIM,
        qualityLabel: `preview-${PREVIEW_MAX_DIM}`,
        prefetchNeighbors: true,
        priority: 120,
      });
    }, 80);
  };

  const handleSliceCommit = (value) => {
    if (!activeInstanceId) return;
    const nextIndex = clampSliceIndex(value, axisTotal || totalLayers);
    setSliderZ(nextIndex);
    setCommittedZ(nextIndex);
    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
      previewDebounceRef.current = null;
    }
    isScrubbingRef.current = false;
  };

  const handleAxisChange = (nextAxis) => {
    const axisValue = nextAxis || "xy";
    isScrubbingRef.current = false;
    localStorage.setItem("mask-proofreading-axis", axisValue);
    setViewAxis(axisValue);
    const axisIndex = clampSliceIndex(
      getAxisIndexForInstance(activeInstance, axisValue),
      axisTotal || totalLayers,
    );
    setViewState((prev) => ({ ...prev, zIndex: axisIndex, axis: axisValue }));
    setSliderZ(axisIndex);
    setCommittedZ(axisIndex);
  };

  const handleSaveMask = async (maskBase64) => {
    if (!sessionId || !activeInstanceId) return;
    setSavingMask(true);
    try {
      await apiClient.post("/eh/detection/instance-mask", {
        session_id: sessionId,
        instance_id: activeInstanceId,
        axis: viewAxis,
        z_index: viewState.zIndex,
        mask_base64: maskBase64,
        ui_state: {
          axis: viewAxis,
          overlay_all_alpha: overlayAllAlpha,
          overlay_active_alpha: overlayActiveAlpha,
          last_instance_id: activeInstanceId,
          last_slice_index: sliderZ ?? viewState.zIndex,
        },
      });
      message.success("Instance mask updated");
      refreshPersistenceStatus();
      loadInstanceView(
        activeInstanceId,
        viewState.zIndex,
        true,
        undefined,
        viewAxis,
      );
    } catch (error) {
      console.error("Failed to save mask:", error);
      message.error(getErrorMessage(error, "Failed to save mask"));
    } finally {
      setSavingMask(false);
    }
  };

  const openExportModal = () => {
    const artifactPath = persistence?.artifact_path;
    if (artifactPath && artifactPath.endsWith(".tif")) {
      setExportPath(artifactPath.replace(".tif", ".exported.tif"));
    } else if (artifactPath && artifactPath.endsWith(".tiff")) {
      setExportPath(artifactPath.replace(".tiff", ".exported.tif"));
    } else {
      setExportPath("");
    }
    setShowExportModal(true);
  };

  const handleExportMasks = async () => {
    const output = exportPath?.trim();
    if (!output) {
      message.warning("Enter an output path to export edited masks.");
      return;
    }
    setExportingMasks(true);
    try {
      const response = await apiClient.post("/eh/detection/export-masks", {
        session_id: sessionId,
        mode: "new_file",
        output_path: output,
        create_backup: true,
      });
      setShowExportModal(false);
      message.success(`Exported masks to ${response.data.written_path}`);
      if (response.data.backup_path) {
        message.info(`Backup created at ${response.data.backup_path}`);
      }
      refreshPersistenceStatus();
    } catch (error) {
      Modal.error({
        title: "Export failed",
        content: getErrorMessage(error, "Unable to export edited masks."),
        okText: "OK",
      });
    } finally {
      setExportingMasks(false);
    }
  };

  const handleOverwriteSource = () => {
    Modal.confirm({
      title: "Overwrite source masks?",
      content:
        "This writes your edited masks back to the original source and always creates a timestamped backup first.",
      okText: "Overwrite with backup",
      okButtonProps: { danger: true, loading: overwritingSource },
      cancelText: "Cancel",
      onOk: async () => {
        setOverwritingSource(true);
        try {
          const response = await apiClient.post("/eh/detection/export-masks", {
            session_id: sessionId,
            mode: "overwrite_source",
            create_backup: true,
          });
          message.success(`Source masks updated at ${response.data.written_path}`);
          if (response.data.backup_path) {
            message.info(`Backup created at ${response.data.backup_path}`);
          }
          refreshPersistenceStatus();
        } catch (error) {
          Modal.error({
            title: "Overwrite failed",
            content: getErrorMessage(
              error,
              "Unable to overwrite source masks safely.",
            ),
            okText: "OK",
          });
        } finally {
          setOverwritingSource(false);
        }
      },
    });
  };

  if (!sessionId) {
    return (
      <div style={{ padding: "24px 0" }}>
        <DatasetLoader onLoad={handleDatasetLoad} loading={loadingInstances} />
      </div>
    );
  }

  const currentSliceIndex = clampSliceIndex(
    sliderZ ?? viewState.zIndex,
    axisTotal || totalLayers,
  );

  const reviewControls =
    activeInstance && instanceMode !== "none" ? (
      <div style={{ display: "grid", gap: 8 }}>
        <Text style={{ fontSize: 13, fontWeight: 600 }}>
          Instance #{activeInstance.id}
        </Text>
        <Space size="small" wrap>
          <Button
            size="small"
            type="primary"
            loading={classificationPending}
            disabled={classificationPending}
            onClick={() => handleInstanceClassify("correct")}
          >
            Looks good
          </Button>
          <Button
            size="small"
            danger
            loading={classificationPending}
            disabled={classificationPending}
            onClick={() => handleInstanceClassify("incorrect")}
          >
            Needs fix
          </Button>
          <Button
            size="small"
            style={{ background: "#f59e0b", color: "#fff" }}
            loading={classificationPending}
            disabled={classificationPending}
            onClick={() => handleInstanceClassify("unsure")}
          >
            Unsure
          </Button>
        </Space>
      </div>
    ) : (
      <Text type="secondary" style={{ fontSize: 12 }}>
        Select an instance to review.
      </Text>
    );

  const viewControls = (
    <div>
      <Text style={{ fontSize: 12 }}>Other instances</Text>
      <Slider
        min={0}
        max={100}
        value={Math.round(overlayAllAlpha * 100)}
        onChange={(value) => setOverlayAllAlpha(value / 100)}
      />
      <Text style={{ fontSize: 12 }}>Selected instance</Text>
      <Slider
        min={0}
        max={100}
        value={Math.round(overlayActiveAlpha * 100)}
        onChange={(value) => setOverlayActiveAlpha(value / 100)}
      />
    </div>
  );

  const instanceControls =
    instanceMode !== "none" && instances.length > 0 ? (
      <div style={{ display: "grid", gap: 8 }}>
        <Space size="small" wrap>
          <Button size="small" type="primary" onClick={() => setShowInstanceBrowser(true)}>
            Browse...
          </Button>
          <Button size="small" onClick={goToNextUnreviewed}>
            Next unreviewed
          </Button>
          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                {
                  key: "export",
                  label: "Export edited masks...",
                  onClick: openExportModal,
                },
                {
                  key: "overwrite",
                  label: "Overwrite source masks...",
                  danger: true,
                  onClick: handleOverwriteSource,
                },
              ],
            }}
          >
            <Button size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
        <Space size="small" align="center">
          <Text type="secondary" style={{ fontSize: 12 }}>
            Instances
          </Text>
          <Tag style={{ margin: 0 }}>{instances.length}</Tag>
        </Space>
      </div>
    ) : (
      <Text type="secondary" style={{ fontSize: 12 }}>
        No instances available.
      </Text>
    );

  const inspectorItems = [
    { key: "review", label: "Review", children: reviewControls },
    { key: "instances", label: "Instances", children: instanceControls },
    { key: "view", label: "View", children: viewControls },
    {
      key: "progress",
      label: "Progress",
      children: (
        <ProgressTracker
          stats={stats}
          projectName={projectName}
          totalLayers={instances.length}
          unitLabel="instances"
          compact
          onNewSession={() => {
            setSessionId(null);
            setActiveInstanceId(null);
            setInstances([]);
            setPersistence(null);
          }}
          onJumpToNext={goToNextUnreviewed}
        />
      ),
    },
  ];

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
            marginBottom: 10,
          }}
        >
          <Title level={5} style={{ margin: 0 }}>
            Instance proofreading
          </Title>
          <Space size="small">
            <Button
              size="small"
              type={showInspector ? "default" : "primary"}
              onClick={() => setShowInspector((prev) => !prev)}
            >
              {showInspector ? "Focus canvas" : "Show sidebar"}
            </Button>
          </Space>
        </div>

        <Layout style={{ background: "transparent", position: "relative" }}>
          <Content style={{ padding: showInspector ? "0 14px 0 0" : 0 }}>
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
                <ProofreadingEditor
                  imageBase64={viewState.imageBase64}
                  maskBase64={viewState.maskRawBase64}
                  overlayAllBase64={viewState.maskAllBase64}
                  overlayActiveBase64={viewState.maskActiveBase64}
                  overlayAllAlpha={overlayAllAlpha}
                  overlayActiveAlpha={overlayActiveAlpha}
                  loading={loadingView || loadingInstances}
                  axis={viewAxis}
                  axisOptions={axisOptions}
                  onAxisChange={handleAxisChange}
                  activeInstanceId={activeInstanceId}
                  onSave={handleSaveMask}
                  onNext={() =>
                    handleSliceCommit(
                      Math.min(
                        currentSliceIndex + 1,
                        (axisTotal || totalLayers) - 1,
                      ),
                    )
                  }
                  onPrevious={() =>
                    handleSliceCommit(Math.max(currentSliceIndex - 1, 0))
                  }
                  currentLayer={currentSliceIndex}
                  totalLayers={axisTotal || totalLayers}
                  layerName={`${viewAxis.toUpperCase()} ${currentSliceIndex + 1}`}
                  minimalChrome
                />
                <div style={{ marginTop: 16 }}>
                  <Slider
                    min={0}
                    max={Math.max((axisTotal || totalLayers) - 1, 0)}
                    value={currentSliceIndex}
                    onChange={handleSliceChange}
                    onAfterChange={handleSliceCommit}
                    tooltip={{
                      formatter: (value) =>
                        `${viewAxis.toUpperCase()} ${value + 1}`,
                    }}
                  />
                </div>
                {savingMask && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">Saving mask…</Text>
                  </div>
                )}
              </>
            )}
          </Content>

          {showInspector && (
            <Sider
              width={Math.max(260, Math.min(360, windowWidth * 0.3))}
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
                    padding: "0 2px 2px",
                    borderBottom: "1px solid #eef2f7",
                  }}
                >
                  <Space size={8} align="center">
                    <Text
                      type="secondary"
                      style={{
                        fontSize: 11,
                        letterSpacing: 0.6,
                        textTransform: "uppercase",
                      }}
                    >
                      {viewAxis.toUpperCase()}
                    </Text>
                    <Text style={{ fontSize: 14, fontWeight: 500 }}>
                      Slice {currentSliceIndex + 1}
                    </Text>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {axisTotal || totalLayers} slices
                  </Text>
                </div>
                <Collapse
                  bordered={false}
                  size="small"
                  activeKey={inspectorSections}
                  onChange={(keys) =>
                    setInspectorSections(Array.isArray(keys) ? keys : [keys])
                  }
                  items={inspectorItems}
                />
              </div>
            </Sider>
          )}
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
      <Modal
        title="Export edited masks"
        open={showExportModal}
        onCancel={() => setShowExportModal(false)}
        onOk={handleExportMasks}
        confirmLoading={exportingMasks}
        okText="Export"
      >
        <div style={{ display: "grid", gap: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Choose where to write a TIFF containing the current edited instance
            volume.
          </Text>
          <Input
            value={exportPath}
            onChange={(event) => setExportPath(event.target.value)}
            placeholder="/path/to/edited_masks.tif"
          />
        </div>
      </Modal>
    </Layout>
  );
}

export default DetectionWorkflow;
