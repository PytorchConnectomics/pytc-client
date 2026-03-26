import axios from "axios";
import { message } from "antd";
import yaml from "js-yaml";
import {
  setInferenceExecutionDefaults,
  setInferenceOutputPath,
  setTrainingOutputPath,
} from "./configSchema";

const BASE_URL = `${process.env.REACT_APP_SERVER_PROTOCOL || "http"}://${process.env.REACT_APP_SERVER_URL || "localhost:4242"}`;

// Guest-mode requests do not rely on cookies, so keep CORS requests non-credentialed.
export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: false,
});

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

export async function getNeuroglancerViewer(image, label, scales) {
  try {
    const url = `${BASE_URL}/neuroglancer`;
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
      const res = await axios.post(url, formData);
      return res.data;
    }

    const data = JSON.stringify({
      image: buildFilePath(image),
      label: buildFilePath(label),
      scales,
    });
    const res = await axios.post(url, data);
    return res.data;
  } catch (error) {
    message.error(
      'Invalid Data Path(s). Be sure to include all "/" and that data path is correct.',
    );
  }
}

export async function checkFile(file) {
  try {
    const url = `${BASE_URL}/check_files`;
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
    const fullUrl = `${BASE_URL}/${url}`;
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
) {
  try {
    console.log("[API] ===== Starting Training Configuration =====");
    console.log("[API] logPath:", logPath);
    console.log("[API] outputPath:", outputPath);

    // Parse the YAML config and inject the outputPath
    let configToSend = trainingConfig;

    if (outputPath && trainingConfig) {
      try {
        const configObj = yaml.load(trainingConfig) || {};
        setTrainingOutputPath(configObj, outputPath);

        configToSend = yaml.dump(configObj);
        console.log("[API] Injected training output path:", outputPath);
        console.log(
          "[API] Modified config preview:",
          configToSend.substring(0, 500),
        );
      } catch (e) {
        console.warn(
          "[API] Failed to parse/modify YAML, using original config:",
          e,
        );
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
    });

    console.log("[API] Request payload size:", data.length, "bytes");
    console.log("[API] Note: TensorBoard will monitor outputPath, not logPath");
    console.log("[API] =========================================");

    return makeApiRequest("start_model_training", "post", data);
  } catch (error) {
    handleError(error);
  }
}

export async function stopModelTraining() {
  try {
    await axios.post(`${BASE_URL}/stop_model_training`);
  } catch (error) {
    handleError(error);
  }
}

export async function getTrainingStatus() {
  try {
    const res = await axios.get(`${BASE_URL}/training_status`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getTrainingLogs() {
  try {
    const res = await axios.get(`${BASE_URL}/training_logs`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getTensorboardURL() {
  return makeApiRequest("get_tensorboard_url", "get");
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
) {
  console.log("\n========== API.JS: START_MODEL_INFERENCE CALLED ==========");
  console.log("[API] Function arguments:");
  console.log("[API]   - inferenceConfig type:", typeof inferenceConfig);
  console.log(
    "[API]   - inferenceConfig length:",
    inferenceConfig?.length || "N/A",
  );
  console.log("[API]   - outputPath:", outputPath);
  console.log("[API]   - outputPath type:", typeof outputPath);
  console.log("[API]   - checkpointPath:", checkpointPath);
  console.log("[API]   - checkpointPath type:", typeof checkpointPath);

  try {
    console.log("[API] ===== Starting Inference Configuration =====");

    // Parse the YAML config and inject the outputPath
    let configToSend = inferenceConfig;

    if (inferenceConfig) {
      try {
        console.log("[API] Parsing YAML config...");
        const configObj = yaml.load(inferenceConfig) || {};
        console.log("[API] ✓ YAML parsed successfully");

        if (outputPath) {
          setInferenceOutputPath(configObj, outputPath);
          console.log("[API] ✓ Injected inference output path:", outputPath);
        }
        setInferenceExecutionDefaults(configObj);
        console.log("[API] ✓ Applied inference runtime defaults");

        // Convert back to YAML
        console.log("[API] Converting back to YAML...");
        configToSend = yaml.dump(configObj);
        console.log("[API] ✓ YAML conversion successful");
        console.log(
          "[API] Modified config preview (first 500 chars):",
          configToSend.substring(0, 500),
        );
      } catch (e) {
        console.error("[API] ✗ YAML processing error:", e);
        console.error("[API] Error type:", e.constructor.name);
        console.error("[API] Error message:", e.message);
        console.warn("[API] Falling back to original config");
        configToSend = inferenceConfig;
      }
    } else {
      console.warn(
        "[API] ⚠ No inferenceConfig provided, request will use raw payload value",
      );
    }

    console.log("[API] Building request payload...");
    const payload = {
      arguments: {
        checkpoint: checkpointPath,
      },
      outputPath,
      inferenceConfig: configToSend,
      configOriginPath,
    };

    console.log("[API] Payload structure:");
    console.log(
      "[API]   - arguments.checkpoint:",
      payload.arguments.checkpoint,
    );
    console.log("[API]   - outputPath:", payload.outputPath);
    console.log(
      "[API]   - inferenceConfig length:",
      payload.inferenceConfig?.length,
    );

    const data = JSON.stringify(payload);
    console.log("[API] Request payload size:", data.length, "bytes");
    console.log(
      "[API] JSON payload preview (first 300 chars):",
      data.substring(0, 300),
    );

    console.log("[API] Calling makeApiRequest...");
    console.log("[API] Target endpoint: start_model_inference");
    console.log("[API] Method: POST");
    console.log("[API] =========================================");

    const result = await makeApiRequest("start_model_inference", "post", data);
    console.log("[API] ✓ makeApiRequest returned:", result);
    console.log("========== API.JS: END START_MODEL_INFERENCE ==========\n");
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
    const res = await axios.get(`${BASE_URL}/inference_status`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getInferenceLogs() {
  try {
    const res = await axios.get(`${BASE_URL}/inference_logs`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function stopModelInference() {
  try {
    await axios.post(`${BASE_URL}/stop_model_inference`);
  } catch (error) {
    handleError(error);
  }
}

export async function queryChatBot(query, conversationId) {
  try {
    const res = await axios.post(`${BASE_URL}/chat/query`, {
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
    await axios.post(`${BASE_URL}/chat/clear`);
  } catch (error) {
    handleError(error);
  }
}

// ── Conversation history endpoints ───────────────────────────────────────────

export async function listConversations() {
  try {
    const res = await axios.get(`${BASE_URL}/chat/conversations`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function createConversation() {
  try {
    const res = await axios.post(`${BASE_URL}/chat/conversations`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function getConversation(convoId) {
  try {
    const res = await axios.get(`${BASE_URL}/chat/conversations/${convoId}`);
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function deleteConversation(convoId) {
  try {
    await axios.delete(`${BASE_URL}/chat/conversations/${convoId}`);
  } catch (error) {
    handleError(error);
  }
}

export async function updateConversationTitle(convoId, title) {
  try {
    const res = await axios.patch(`${BASE_URL}/chat/conversations/${convoId}`, {
      title,
    });
    return res.data;
  } catch (error) {
    handleError(error);
  }
}

export async function queryHelperChat(taskKey, query, fieldContext) {
  try {
    const res = await axios.post(`${BASE_URL}/chat/helper/query`, {
      taskKey,
      query,
      fieldContext,
    });
    return res.data?.response;
  } catch (error) {
    handleError(error);
  }
}

export async function clearHelperChat(taskKey) {
  try {
    await axios.post(`${BASE_URL}/chat/helper/clear`, { taskKey });
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
