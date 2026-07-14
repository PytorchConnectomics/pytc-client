import axios from "axios";
import yaml from "js-yaml";
import { logClientEvent } from "./logging/appEventLog";
import {
  detectConfigDiagnostics,
  summarizeConfigText,
} from "./logging/configLogSummary";
import {
  setInferenceExecutionDefaults,
  setInferenceOutputPath,
  setTrainingOutputPath,
} from "./configSchema";

const API_LEGACY_PREFIXES = [
  "/api/workflows",
  "/api/files",
  "/api/app",
];

const removeTrailingSlash = (value) => value.replace(/\/+$/, "");

const getDefaultBaseUrl = () => {
  if (
    typeof window !== "undefined" &&
    window.location?.origin &&
    !window.location.hostname.match(/^(localhost|127\.0\.0\.1)$/)
  ) {
    return `${window.location.origin}/api`;
  }

  return `${process.env.REACT_APP_SERVER_PROTOCOL || "http"}://${process.env.REACT_APP_SERVER_URL || "localhost:4242"}`;
};

const BASE_URL = removeTrailingSlash(
  process.env.REACT_APP_API_BASE_URL || getDefaultBaseUrl(),
);

const getBasePath = (baseUrl) => {
  if (!baseUrl) return "";
  const protocolMatch = baseUrl.match(/^[a-z][a-z\d+\-.]*:\/\//i);
  if (protocolMatch && protocolMatch.index === 0) {
    try {
      return new URL(baseUrl).pathname || "";
    } catch {}
  }

  const originEnd = baseUrl.indexOf("/");
  return originEnd === -1 ? "" : baseUrl.slice(originEnd);
};

const BASE_PATH = getBasePath(BASE_URL);
const getLegacyApiBasePrefix = (basePath) => {
  const candidates = [...API_LEGACY_PREFIXES, "/api"];
  return candidates.find(
    (prefix) =>
      basePath === prefix ||
      basePath.startsWith(`${prefix}/`) ||
      basePath.startsWith(`${prefix}?`) ||
      basePath.startsWith(`${prefix}#`),
  ) || null;
};

const BASE_LEGACY_API_PREFIX =
  getLegacyApiBasePrefix(BASE_PATH) || getLegacyApiBasePrefix(BASE_URL);

const shouldStripLegacyApiPrefix = (path) => {
  const normalizedPath = path.startsWith("/")
    ? path
    : `/${String(path || "")}`;

  if (!BASE_LEGACY_API_PREFIX) return false;
  if (BASE_LEGACY_API_PREFIX === "/api") {
    return (
      normalizedPath === "/api" ||
      normalizedPath.startsWith("/api/") ||
      normalizedPath.startsWith("/api?") ||
      normalizedPath.startsWith("/api#")
    );
  }

  return (
    normalizedPath === BASE_LEGACY_API_PREFIX ||
    normalizedPath.startsWith(`${BASE_LEGACY_API_PREFIX}/`) ||
    normalizedPath.startsWith(`${BASE_LEGACY_API_PREFIX}?`) ||
    normalizedPath.startsWith(`${BASE_LEGACY_API_PREFIX}#`)
  );
};

const canonicalizeApiPath = (path) => {
  const normalized = String(path || "");
  const match = normalized.match(/^([^?#]*)([?#].*)?$/);
  const rawPath = match?.[1] || "";
  const suffix = match?.[2] || "";
  const normalizedPath = rawPath.startsWith("/") ? rawPath : `/${rawPath}`;

  if (!shouldStripLegacyApiPrefix(normalizedPath)) {
    return `${normalizedPath}${suffix}`;
  }

  const stripLength = BASE_LEGACY_API_PREFIX?.length || 0;
  const deduped = normalizedPath.length > stripLength
    ? normalizedPath.slice(stripLength)
    : "/";
  return `${deduped}${suffix}`;
};

export const buildApiUrl = (path) => `${BASE_URL}${canonicalizeApiPath(path)}`;

const DEBUG_API_LOGS =
  process.env.REACT_APP_DEBUG_API_LOGS === "1" ||
  process.env.REACT_APP_DEBUG_API_LOGS === "true";

const apiDebugLog = (...args) => {
  if (DEBUG_API_LOGS) {
    console.log(...args);
  }
};

// Create axios instance without auth headers—app runs as guest by default.
export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
});

const summarizePayload = (payload) => {
  if (!payload) return { hasBody: false };
  if (typeof payload === "string") {
    return { hasBody: true, bodyLength: payload.length };
  }
  if (payload instanceof FormData) {
    return { hasBody: true, bodyType: "FormData" };
  }
  if (typeof payload === "object") {
    return {
      hasBody: true,
      bodyType: Array.isArray(payload) ? "array" : "object",
      keys: Object.keys(payload).slice(0, 20),
    };
  }
  return { hasBody: true, bodyType: typeof payload };
};

const attachApiLogging = (instance, source) => {
  instance.interceptors.request.use(
    (config) => {
      config.metadata = {
        startedAt:
          typeof performance !== "undefined" ? performance.now() : Date.now(),
      };
      logClientEvent("api_request", {
        level: "INFO",
        message: `${String(config.method || "get").toUpperCase()} ${config.url}`,
        source,
        data: {
          method: String(config.method || "get").toUpperCase(),
          url: config.url,
          baseURL: config.baseURL,
          ...summarizePayload(config.data),
        },
      });
      return config;
    },
    (error) => {
      logClientEvent("api_request_setup_failed", {
        level: "ERROR",
        message: error.message || "Axios request setup failed",
        source,
        data: { error: error.message },
      });
      return Promise.reject(error);
    },
  );

  instance.interceptors.response.use(
    (response) => {
      const startedAt = response.config?.metadata?.startedAt;
      const endedAt =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      logClientEvent("api_response", {
        level: "INFO",
        message: `${String(response.config?.method || "get").toUpperCase()} ${response.config?.url} -> ${response.status}`,
        source,
        data: {
          method: String(response.config?.method || "get").toUpperCase(),
          url: response.config?.url,
          status: response.status,
          latencyMs:
            startedAt !== undefined ? Number((endedAt - startedAt).toFixed(2)) : null,
        },
      });
      return response;
    },
    (error) => {
      const config = error.config || {};
      const startedAt = config.metadata?.startedAt;
      const endedAt =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      logClientEvent("api_response_error", {
        level: "ERROR",
        message:
          error.message ||
          `${String(config.method || "get").toUpperCase()} ${config.url} failed`,
        source,
        data: {
          method: String(config.method || "get").toUpperCase(),
          url: config.url,
          status: error.response?.status,
          latencyMs:
            startedAt !== undefined ? Number((endedAt - startedAt).toFixed(2)) : null,
          detail: error.response?.data?.detail || null,
        },
      });
      return Promise.reject(error);
    },
  );
};

attachApiLogging(apiClient, "apiClient");
attachApiLogging(axios, "axios");

const buildFilePath = (file) => {
  if (!file) return "";
  if (typeof file === "string") return file;
  if (file.folderPath) return file.folderPath + file.name;
  if (file.path) return file.path;
  if (file.originFileObj && file.originFileObj.path) {
    return file.originFileObj.path;
  }
  return file.name;
};

const hasBrowserFile = (file) => file && file.originFileObj instanceof File;

const getErrorDetailMessage = (detail) => {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(getErrorDetailMessage).filter(Boolean).join("; ");
  }
  if (typeof detail === "object") {
    if (detail.user_message) {
      return getErrorDetailMessage(detail.user_message);
    }
    const nestedUpstream =
      detail.upstream_body !== undefined
        ? getErrorDetailMessage(detail.upstream_body)
        : "";
    return [
      detail.message,
      detail.detail,
      detail.reason,
      nestedUpstream,
      detail.error,
    ]
      .filter(Boolean)
      .join(" | ");
  }
  return String(detail);
};

export async function getNeuroglancerViewer(image, label, scales, workflowId = null) {
  try {
    const url = buildApiUrl("/neuroglancer");
    if (hasBrowserFile(image)) {
      const formData = new FormData();
      formData.append(
        "image",
        image.originFileObj,
        image.originFileObj.name || image.name || "image",
      );
      if (label && hasBrowserFile(label)) {
        formData.append(
          "label",
          label.originFileObj,
          label.originFileObj.name || label.name || "label",
        );
      }
      formData.append("scales", JSON.stringify(scales));
      if (workflowId) {
        formData.append("workflow_id", String(workflowId));
      }
      const res = await axios.post(url, formData);
      return res.data;
    }

    const data = JSON.stringify({
      image: buildFilePath(image),
      label: buildFilePath(label),
      scales,
      workflow_id: workflowId,
    });
    const res = await axios.post(url, data);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getNeuroglancerProofreadingViewer({
  image,
  label,
  scales,
  workflowId = null,
  sessionId = null,
  activeInstanceId = null,
  initialVoxel = null,
} = {}) {
  try {
    const url = buildApiUrl("/neuroglancer/proofread");
    const res = await axios.post(
      url,
      JSON.stringify({
        image: buildFilePath(image),
        label: buildFilePath(label),
        scales,
        workflow_id: workflowId,
        session_id: sessionId,
        active_instance_id: activeInstanceId,
        initial_voxel: initialVoxel,
      }),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getInstanceVolumePreview(
  sessionId,
  instanceId,
  maxPoints = 30000,
) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath("/eh/detection/instance-volume-preview"),
      {
        params: {
          session_id: sessionId,
          instance_id: instanceId,
          max_points: maxPoints,
        },
      },
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getInstanceMeshPreview(
  sessionId,
  instanceId,
  maxFaces = 60000,
) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath("/eh/detection/instance-mesh-preview"),
      {
        params: {
          session_id: sessionId,
          instance_id: instanceId,
          max_faces: maxFaces,
        },
      },
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function checkFile(file) {
  try {
    const url = buildApiUrl("/check_files");
    const data = JSON.stringify({
      folderPath: file.folderPath || "",
      name: file.name,
      filePath: file.path || file.originFileObj?.path,
    });
    const res = await axios.post(url, data);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

function handleError(error) {
  if (error.response) {
    const detail = error.response.data?.detail;
    const detailMessage = getErrorDetailMessage(detail);
    throw new Error(
      `${error.response.status}: ${detailMessage || error.response.statusText}`,
    );
  }
  throw error;
}

export async function makeApiRequest(url, method, data = null) {
  try {
    const fullUrl = buildApiUrl(url);
    const config = {
      method,
      url: fullUrl,
      headers: {
        "Content-Type": "application/json",
      },
    };

    if (data) {
      config.data = data;
    }

    const res = await axios(config);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function startModelTraining(
  trainingConfig,
  logPath,
  outputPath,
  configOriginPath = "",
  workflowId = null,
  autoParameters = false,
  inputImagePath = "",
  inputLabelPath = "",
) {
  try {
    apiDebugLog("[API] ===== Starting Training Configuration =====");
    apiDebugLog("[API] logPath:", logPath);
    apiDebugLog("[API] outputPath:", outputPath);

    // Parse the YAML config and inject the outputPath
    let configToSend = trainingConfig;

    if (outputPath && trainingConfig) {
      try {
        const configObj = yaml.load(trainingConfig) || {};
        setTrainingOutputPath(configObj, outputPath);

        configToSend = yaml.dump(configObj);
        apiDebugLog("[API] Injected training output path:", outputPath);
        apiDebugLog(
          "[API] Modified config preview:",
          configToSend.substring(0, 500),
        );
      } catch (e) {
        console.warn(
          "[API] Failed to parse/modify YAML, using original config:",
          e,
        );
        logClientEvent("training_config_transform_failed", {
          level: "WARNING",
          message: "Failed to transform training config before request",
          source: "api",
          data: {
            error: e.message || "unknown error",
            configOriginPath,
            outputPath,
            logPath,
            workflowId,
          },
        });
      }
    } else {
      console.warn(
        "[API] No outputPath provided, config will use its original OUTPUT_PATH",
      );
    }

    const data = JSON.stringify({
      logPath, // Keep for backwards compatibility, but won't be used for TensorBoard
      outputPath, // TensorBoard will use this instead
      trainingConfig: configToSend,
      configOriginPath,
      workflow_id: workflowId,
      autoParameters: Boolean(autoParameters),
      auto_parameters: Boolean(autoParameters),
      inputImagePath,
      inputLabelPath,
    });

    apiDebugLog("[API] Request payload size:", data.length, "bytes");
    apiDebugLog("[API] Note: TensorBoard will monitor outputPath, not logPath");
    apiDebugLog("[API] =========================================");

    const configSummary = summarizeConfigText(configToSend, "training");
    const diagnostics = detectConfigDiagnostics(configSummary);
    logClientEvent("training_api_payload_prepared", {
      level: diagnostics.length ? "WARNING" : "INFO",
      message: "Training API payload prepared",
      source: "api",
      data: {
        workflowId,
        configOriginPath,
        outputPath,
        logPath,
        inputImagePath,
        inputLabelPath,
        autoParameters: Boolean(autoParameters),
        requestBytes: data.length,
        configSummary,
        diagnostics,
      },
    });

    return makeApiRequest("start_model_training", "post", data);
  } catch (error) {
    handleError(error);
  }
}

export async function stopModelTraining() {
  try {
    await axios.post(buildApiUrl("/stop_model_training"));
  } catch (error) {
    handleError(error);
  }
}

export async function getTrainingStatus() {
  try {
    const res = await axios.get(buildApiUrl("/training_status"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getTrainingLogs() {
  try {
    const res = await axios.get(buildApiUrl("/training_logs"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getTensorboardURL() {
  return makeApiRequest("get_tensorboard_url", "get");
}

export async function getTensorboardStatus() {
  return makeApiRequest("get_tensorboard_status", "get");
}

export async function startTensorboard(logPath) {
  const query = logPath
    ? `?${new URLSearchParams({ logPath }).toString()}`
    : "";
  return makeApiRequest(`start_tensorboard${query}`, "get");
}

export async function startModelInference(
  inferenceConfig,
  outputPath,
  checkpointPath,
  configOriginPath = "",
  workflowId = null,
  inputImagePath = "",
) {
  apiDebugLog("\n========== API.JS: START_MODEL_INFERENCE CALLED ==========");
  apiDebugLog("[API] Function arguments:");
  apiDebugLog("[API]   - inferenceConfig type:", typeof inferenceConfig);
  apiDebugLog(
    "[API]   - inferenceConfig length:",
    inferenceConfig?.length || "N/A",
  );
  apiDebugLog("[API]   - outputPath:", outputPath);
  apiDebugLog("[API]   - outputPath type:", typeof outputPath);
  apiDebugLog("[API]   - checkpointPath:", checkpointPath);
  apiDebugLog("[API]   - checkpointPath type:", typeof checkpointPath);

  try {
    apiDebugLog("[API] ===== Starting Inference Configuration =====");

    // Parse the YAML config and inject the outputPath
    let configToSend = inferenceConfig;

    if (inferenceConfig) {
      try {
        apiDebugLog("[API] Parsing YAML config...");
        const configObj = yaml.load(inferenceConfig) || {};
        apiDebugLog("[API] ✓ YAML parsed successfully");

        if (outputPath) {
          setInferenceOutputPath(configObj, outputPath);
          apiDebugLog("[API] ✓ Injected inference output path:", outputPath);
        }
        setInferenceExecutionDefaults(configObj);
        apiDebugLog("[API] ✓ Applied inference runtime defaults");

        // Convert back to YAML
        apiDebugLog("[API] Converting back to YAML...");
        configToSend = yaml.dump(configObj);
        apiDebugLog("[API] ✓ YAML conversion successful");
        apiDebugLog(
          "[API] Modified config preview (first 500 chars):",
          configToSend.substring(0, 500),
        );
      } catch (e) {
        console.error("[API] ✗ YAML processing error:", e);
        console.error("[API] Error type:", e.constructor.name);
        console.error("[API] Error message:", e.message);
        console.warn("[API] Falling back to original config");
        logClientEvent("inference_config_transform_failed", {
          level: "WARNING",
          message: "Failed to transform inference config before request",
          source: "api",
          data: {
            error: e.message || "unknown error",
            configOriginPath,
            outputPath,
            checkpointPath,
            workflowId,
          },
        });
        configToSend = inferenceConfig;
      }
    } else {
      console.warn(
        "[API] ⚠ No inferenceConfig provided, request will use raw payload value",
      );
    }

    apiDebugLog("[API] Building request payload...");
    const payload = {
      arguments: {
        checkpoint: checkpointPath,
      },
      outputPath,
      inputImagePath,
      inferenceConfig: configToSend,
      configOriginPath,
      workflow_id: workflowId,
    };

    apiDebugLog("[API] Payload structure:");
    apiDebugLog(
      "[API]   - arguments.checkpoint:",
      payload.arguments.checkpoint,
    );
    apiDebugLog("[API]   - outputPath:", payload.outputPath);
    apiDebugLog(
      "[API]   - inferenceConfig length:",
      payload.inferenceConfig?.length,
    );

    const data = JSON.stringify(payload);
    apiDebugLog("[API] Request payload size:", data.length, "bytes");
    apiDebugLog(
      "[API] JSON payload preview (first 300 chars):",
      data.substring(0, 300),
    );

    const configSummary = summarizeConfigText(configToSend, "inference");
    const diagnostics = detectConfigDiagnostics(configSummary);
    logClientEvent("inference_api_payload_prepared", {
      level: diagnostics.length ? "WARNING" : "INFO",
      message: "Inference API payload prepared",
      source: "api",
      data: {
        workflowId,
        configOriginPath,
        outputPath,
        checkpointPath,
        requestBytes: data.length,
        configSummary,
        diagnostics,
      },
    });

    apiDebugLog("[API] Calling makeApiRequest...");
    apiDebugLog("[API] Target endpoint: start_model_inference");
    apiDebugLog("[API] Method: POST");
    apiDebugLog("[API] =========================================");

    const result = await makeApiRequest("start_model_inference", "post", data);
    apiDebugLog("[API] ✓ makeApiRequest returned:", result);
    apiDebugLog("========== API.JS: END START_MODEL_INFERENCE ==========\n");
    return result;
  } catch (error) {
    console.error(
      "========== API.JS: ERROR IN START_MODEL_INFERENCE ==========",
    );
    console.error("[API] Error caught:", error);
    console.error("[API] Error type:", error.constructor.name);
    console.error("[API] Error message:", error.message);
    console.error("[API] Error stack:", error.stack);
    console.error("========== API.JS: END ERROR ==========\n");
    handleError(error);
  }
}

export async function getInferenceStatus() {
  try {
    const res = await axios.get(buildApiUrl("/inference_status"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getInferenceLogs() {
  try {
    const res = await axios.get(buildApiUrl("/inference_logs"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function syncWorkflowInferenceRuntime(workflowId, body = {}) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/sync-inference-runtime`),
      body,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function stopModelInference() {
  try {
    await axios.post(buildApiUrl("/stop_model_inference"));
  } catch (error) {
    handleError(error);
  }
}

export async function queryChatBot(query, conversationId) {
  try {
    const res = await axios.post(buildApiUrl("/chat/query"), {
      query,
      conversationId,
    });
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function clearChat() {
  try {
    await axios.post(buildApiUrl("/chat/clear"));
  } catch (error) {
    handleError(error);
  }
}

// ── Conversation history endpoints ───────────────────────────────────────────

export async function listConversations() {
  try {
    const res = await axios.get(buildApiUrl("/chat/conversations"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function createConversation() {
  try {
    const res = await axios.post(buildApiUrl("/chat/conversations"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getConversation(convoId) {
  try {
    const res = await axios.get(
      buildApiUrl(`/chat/conversations/${convoId}`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function deleteConversation(convoId) {
  try {
    await axios.delete(buildApiUrl(`/chat/conversations/${convoId}`));
  } catch (error) {
    handleError(error);
  }
}

export async function updateConversationTitle(convoId, title) {
  try {
    const res = await axios.patch(
      buildApiUrl(`/chat/conversations/${convoId}`),
      { title },
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function queryHelperChat(taskKey, query, fieldContext, history = []) {
  try {
    const res = await axios.post(buildApiUrl("/chat/helper/query"), {
      taskKey,
      query,
      fieldContext,
      history,
    });
    return res.data?.response;
  } catch (error) {
    handleError(error);
  }
}

export async function clearHelperChat(taskKey) {
  try {
    await axios.post(buildApiUrl("/chat/helper/clear"), { taskKey });
  } catch (error) {
    handleError(error);
  }
}

export async function getConfigPresets() {
  return makeApiRequest("pytc/configs", "get");
}

export async function getConfigPresetContent(path) {
  const url = `pytc/config?path=${encodeURIComponent(path)}`;
  return makeApiRequest(url, "get");
}

export async function getModelArchitectures() {
  return makeApiRequest("pytc/architectures", "get");
}

// ── Project Manager persistence ───────────────────────────────────────────────

export async function getPMData() {
  try {
    const res = await apiClient.get(canonicalizeApiPath("/api/pm/data"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getPMConfig() {
  try {
    const res = await apiClient.get(canonicalizeApiPath("/api/pm/config"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getPMSchema() {
  try {
    const res = await apiClient.get(canonicalizeApiPath("/api/pm/schema"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function updatePMConfig(patch) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath("/api/pm/config"),
      patch,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function savePMData(state) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath("/api/pm/data"),
      state,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function resetPMData() {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath("/api/pm/data/reset"),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function mountProjectDirectory({
  directoryPath,
  mountName = "",
  destinationPath = "root",
}) {
  try {
    const res = await apiClient.post(canonicalizeApiPath("/files/mount"), {
      directory_path: directoryPath,
      mount_name: mountName,
      destination_path: destinationPath,
    });
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function resetFileWorkspace() {
  try {
    const res = await apiClient.delete(canonicalizeApiPath("/files/workspace"));
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

// ── Workflow spine ───────────────────────────────────────────────────────────

export async function getCurrentWorkflow() {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath("/api/workflows/current"),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function updateWorkflow(workflowId, patch) {
  try {
    const res = await apiClient.patch(
      canonicalizeApiPath(`/api/workflows/${workflowId}`),
      patch,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function listWorkflowEvents(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/events`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowHotspots(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/hotspots`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowImpactPreview(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/impact-preview`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowMetrics(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/metrics`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowProjectProgress(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/project-progress`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowOverview(workflowId, { refresh = true } = {}) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/overview`),
      {
        params: { refresh },
      },
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function updateWorkflowProjectProgressVolume(workflowId, body) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/project-progress/volume-status`),
      body,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowAgentRecommendation(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/agent/recommendation`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowPreflight(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/preflight`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function listWorkflowArtifacts(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/artifacts`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function listWorkflowModelRuns(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/model-runs`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function listWorkflowModelVersions(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/model-versions`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function listWorkflowCorrectionSets(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/correction-sets`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function listWorkflowEvaluationResults(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/evaluation-results`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function computeWorkflowEvaluationResult(workflowId, body) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(
        `/api/workflows/${workflowId}/evaluation-results/compute`,
      ),
      body,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function exportWorkflowBundle(workflowId) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/export-bundle`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function startNewWorkflow(body = {}) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath("/api/workflows/current/reset"),
      body,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function appendWorkflowEvent(workflowId, event) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/events`),
      event,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function createAgentAction(workflowId, action) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/agent-actions`),
      action,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function approveAgentAction(workflowId, eventId, overrides = {}) {
  try {
    const hasOverrides =
      overrides && typeof overrides === "object" && Object.keys(overrides).length > 0;
    const res = await apiClient.post(
      canonicalizeApiPath(
        `/api/workflows/${workflowId}/agent-actions/${eventId}/approve`,
      ),
      hasOverrides ? { overrides } : undefined,
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function runWorkflowCommand(workflowId, commandId) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/commands/${commandId}/run`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function rejectAgentAction(workflowId, eventId) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(
        `/api/workflows/${workflowId}/agent-actions/${eventId}/reject`,
      ),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function queryWorkflowAgent(workflowId, query, conversationId = null) {
  try {
    const res = await apiClient.post(
      canonicalizeApiPath(`/api/workflows/${workflowId}/agent/query`),
      {
        query,
        conversation_id: conversationId,
      },
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getWorkflowAgentConversation(workflowId) {
  try {
    const res = await apiClient.get(
      canonicalizeApiPath(`/api/workflows/${workflowId}/agent/conversation`),
    );
    return res.data;
  } catch (error) {
    handleError(error);
  }
}
