import yaml from "js-yaml";
import { startModelInference, startModelTraining } from "../api";
import { applyInputPaths, detectConfigSchema } from "../configSchema";
import { logClientEvent } from "../logging/appEventLog";
import {
  detectConfigDiagnostics,
  summarizeConfigText,
} from "../logging/configLogSummary";

export function getPathValue(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  return value.path || value.originFileObj?.path || value.folderPath || "";
}

function getTrainingConfigOriginPath(trainingState) {
  return (
    trainingState?.configOriginPath ||
    trainingState?.selectedYamlPreset ||
    getPathValue(trainingState?.uploadedYamlFile)
  );
}

function getInferenceConfigOriginPath(inferenceState) {
  return (
    inferenceState?.configOriginPath ||
    inferenceState?.selectedYamlPreset ||
    getPathValue(inferenceState?.uploadedYamlFile)
  );
}

function parseConfigText(configText) {
  if (!configText) return null;
  try {
    const yamlData = yaml.load(configText);
    return yamlData && typeof yamlData === "object" ? yamlData : null;
  } catch (error) {
    return null;
  }
}

function resolveInferenceConfigSource(appContext, overrides = {}) {
  const inferenceState = appContext?.inferenceState || {};
  const trainingState = appContext?.trainingState || {};
  const explicitInferenceConfig = overrides.inferenceConfig;
  const explicitOriginPath = overrides.configOriginPath;
  const inferenceConfig = explicitInferenceConfig ?? appContext?.inferenceConfig;
  const inferenceOriginPath =
    explicitOriginPath || getInferenceConfigOriginPath(inferenceState);
  const trainingConfig = appContext?.trainingConfig;
  const trainingOriginPath = getTrainingConfigOriginPath(trainingState);

  if (explicitInferenceConfig || explicitOriginPath) {
    return {
      configText: inferenceConfig,
      originPath: inferenceOriginPath,
      source: "inference",
      reason: null,
    };
  }

  const inferenceSchema = detectConfigSchema(parseConfigText(inferenceConfig));
  const trainingSchema = detectConfigSchema(parseConfigText(trainingConfig));
  const needsTrainingFallback =
    Boolean(trainingConfig) &&
    (
      !inferenceConfig ||
      (inferenceSchema !== "legacy" && trainingSchema === "legacy") ||
      (
        inferenceOriginPath &&
        inferenceOriginPath.startsWith("tutorials/") &&
        trainingSchema === "legacy"
      )
    );

  if (!needsTrainingFallback) {
    return {
      configText: inferenceConfig,
      originPath: inferenceOriginPath,
      source: "inference",
      reason: null,
    };
  }

  let reason = "missing_inference_config";
  if (inferenceConfig) {
    if (inferenceSchema !== "legacy" && trainingSchema === "legacy") {
      reason = "incompatible_inference_schema";
    } else if (inferenceOriginPath?.startsWith("tutorials/")) {
      reason = "stale_inference_preset";
    }
  }

  logClientEvent("inference_config_fallback_to_training", {
    level: "WARNING",
    message: "Inference launch fell back to the latest training config",
    source: "modelLaunch",
    data: {
      reason,
      inferenceOriginPath,
      trainingOriginPath,
      inferenceSchema,
      trainingSchema,
    },
  });

  return {
    configText: trainingConfig,
    originPath: trainingOriginPath,
    source: "training",
    reason,
  };
}

function prepareConfig(configText, mutator) {
  try {
    const yamlData = yaml.load(configText);
    if (!yamlData || typeof yamlData !== "object") {
      return configText;
    }
    mutator(yamlData);
    return yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
  } catch (error) {
    console.warn("Failed to prepare model launch config:", error);
    logClientEvent("model_launch_config_prepare_failed", {
      level: "WARNING",
      message: "Failed to prepare model launch config",
      source: "modelLaunch",
      data: {
        error: error.message || "unknown error",
        configLength: configText?.length || 0,
      },
    });
    return configText;
  }
}

export function buildTrainingLaunchRequest(
  appContext,
  workflowId = null,
  overrides = {},
) {
  const trainingState = appContext?.trainingState || {};
  const trainingConfig = overrides.trainingConfig ?? appContext?.trainingConfig;

  if (!trainingConfig) {
    throw new Error(
      "Please load a preset or upload a YAML configuration first.",
    );
  }

  const outputPath = getPathValue(overrides.outputPath ?? trainingState.outputPath);
  if (!outputPath) {
    throw new Error("Please set output path first in Step 1.");
  }

  const inputImagePath = getPathValue(
    overrides.inputImagePath ?? trainingState.inputImage,
  );
  const inputLabelPath = getPathValue(
    overrides.inputLabelPath ?? trainingState.inputLabel,
  );
  const logPath =
    getPathValue(overrides.logPath ?? trainingState.logPath) || outputPath;
  const configOriginPath =
    overrides.configOriginPath || getTrainingConfigOriginPath(trainingState);

  const preparedTrainingConfig = prepareConfig(trainingConfig, (yamlData) => {
    applyInputPaths(yamlData, {
      mode: "training",
      inputImagePath,
      inputLabelPath,
      inputPath: "",
      outputPath,
    });
  });
  const configSummary = summarizeConfigText(preparedTrainingConfig, "training");
  const diagnostics = detectConfigDiagnostics(configSummary);

  logClientEvent("training_launch_request_built", {
    level: diagnostics.length ? "WARNING" : "INFO",
    message: "Training launch request built",
    source: "modelLaunch",
    data: {
      workflowId: overrides.workflowId ?? workflowId,
      configOriginPath,
      outputPath,
      logPath,
      inputImagePath,
      inputLabelPath,
      configSummary,
      diagnostics,
    },
  });

  return {
    trainingConfig: preparedTrainingConfig,
    logPath,
    outputPath,
    configOriginPath,
    workflowId: overrides.workflowId ?? workflowId,
  };
}

export async function launchTrainingFromContext(
  appContext,
  workflowId = null,
  overrides = {},
) {
  const request = buildTrainingLaunchRequest(appContext, workflowId, overrides);
  return startModelTraining(
    request.trainingConfig,
    request.logPath,
    request.outputPath,
    request.configOriginPath,
    request.workflowId,
  );
}

export function buildInferenceLaunchRequest(
  appContext,
  workflowId = null,
  overrides = {},
) {
  const inferenceState = appContext?.inferenceState || {};
  const inferenceConfigSource = resolveInferenceConfigSource(appContext, overrides);
  const inferenceConfig = inferenceConfigSource.configText;

  if (!inferenceConfig) {
    throw new Error(
      "Please load or upload an inference configuration first.",
    );
  }

  const checkpointPath = getPathValue(
    overrides.checkpointPath ?? inferenceState.checkpointPath,
  );
  if (!checkpointPath) {
    throw new Error("Please set checkpoint path first.");
  }

  const outputPath = getPathValue(
    overrides.outputPath ?? inferenceState.outputPath,
  );
  const inputImagePath = getPathValue(
    overrides.inputImagePath ?? inferenceState.inputImage,
  );
  const configOriginPath = inferenceConfigSource.originPath;

  const preparedInferenceConfig = prepareConfig(inferenceConfig, (yamlData) => {
    applyInputPaths(yamlData, {
      mode: "inference",
      inputImagePath,
      inputLabelPath: "",
      inputPath: "",
      outputPath,
    });
  });
  const configSummary = summarizeConfigText(preparedInferenceConfig, "inference");
  const diagnostics = detectConfigDiagnostics(configSummary);

  logClientEvent("inference_launch_request_built", {
    level: diagnostics.length ? "WARNING" : "INFO",
    message: "Inference launch request built",
    source: "modelLaunch",
    data: {
      workflowId: overrides.workflowId ?? workflowId,
      configOriginPath,
      configSource: inferenceConfigSource.source,
      configFallbackReason: inferenceConfigSource.reason,
      outputPath,
      checkpointPath,
      inputImagePath,
      configSummary,
      diagnostics,
    },
  });

  return {
    inferenceConfig: preparedInferenceConfig,
    outputPath,
    checkpointPath,
    configOriginPath,
    workflowId: overrides.workflowId ?? workflowId,
  };
}

export async function launchInferenceFromContext(
  appContext,
  workflowId = null,
  overrides = {},
) {
  const request = buildInferenceLaunchRequest(appContext, workflowId, overrides);
  return startModelInference(
    request.inferenceConfig,
    request.outputPath,
    request.checkpointPath,
    request.configOriginPath,
    request.workflowId,
  );
}
