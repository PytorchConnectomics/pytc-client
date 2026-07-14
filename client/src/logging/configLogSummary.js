import yaml from "js-yaml";

const DIRECT_VOLUME_SUFFIXES = [
  ".h5",
  ".hdf5",
  ".hdf",
  ".tif",
  ".tiff",
  ".ome.tif",
  ".ome.tiff",
  ".zarr",
  ".n5",
  ".npy",
  ".npz",
  ".nii",
  ".nii.gz",
  ".mrc",
  ".map",
  ".rec",
  ".png",
  ".jpg",
  ".jpeg",
  ".bmp",
];
const VALID_INFERENCE_AUG_NUMS = [4, 8, 16];

const getNestedValue = (data, path) =>
  path.reduce(
    (current, key) =>
      current && current[key] !== undefined ? current[key] : undefined,
    data,
  );

const trimPath = (value) =>
  typeof value === "string" && value.trim() ? value.trim() : null;

const pathBasename = (value) => {
  const normalized = trimPath(value);
  if (!normalized) return null;
  const segments = normalized.split(/[/\\]/);
  return segments[segments.length - 1] || normalized;
};

const looksLikeDirectVolume = (value) => {
  const normalized = trimPath(value)?.toLowerCase();
  if (!normalized) return false;
  return DIRECT_VOLUME_SUFFIXES.some((suffix) => normalized.endsWith(suffix));
};

export const summarizeConfigObject = (configObj, modeHint = null) => {
  if (!configObj || typeof configObj !== "object") {
    return null;
  }

  const datasetImageName = getNestedValue(configObj, ["DATASET", "IMAGE_NAME"]);
  const datasetLabelName = getNestedValue(configObj, ["DATASET", "LABEL_NAME"]);
  const inferenceImageName = getNestedValue(configObj, ["INFERENCE", "IMAGE_NAME"]);

  return {
    modeHint,
    architecture: getNestedValue(configObj, ["MODEL", "ARCHITECTURE"]) || null,
    blockType: getNestedValue(configObj, ["MODEL", "BLOCK_TYPE"]) || null,
    dataset: {
      imageName: pathBasename(datasetImageName),
      labelName: pathBasename(datasetLabelName),
      outputPath: trimPath(getNestedValue(configObj, ["DATASET", "OUTPUT_PATH"])),
      doChunkTitle: getNestedValue(configObj, ["DATASET", "DO_CHUNK_TITLE"]),
      validRatio: getNestedValue(configObj, ["DATASET", "VALID_RATIO"]),
      rejectSamplingProbability: getNestedValue(configObj, [
        "DATASET",
        "REJECT_SAMPLING",
        "P",
      ]),
      isAbsolutePath: getNestedValue(configObj, ["DATASET", "IS_ABSOLUTE_PATH"]),
      usesDirectVolumePaths:
        looksLikeDirectVolume(datasetImageName) ||
        looksLikeDirectVolume(datasetLabelName),
    },
    inference: {
      imageName: pathBasename(inferenceImageName),
      outputPath: trimPath(getNestedValue(configObj, ["INFERENCE", "OUTPUT_PATH"])),
      augNum: getNestedValue(configObj, ["INFERENCE", "AUG_NUM"]),
      samplesPerBatch: getNestedValue(configObj, [
        "INFERENCE",
        "SAMPLES_PER_BATCH",
      ]),
    },
    solver: {
      baseLr: getNestedValue(configObj, ["SOLVER", "BASE_LR"]),
      batchSize: getNestedValue(configObj, ["SOLVER", "SAMPLES_PER_BATCH"]),
      totalIterations: getNestedValue(configObj, [
        "SOLVER",
        "ITERATION_TOTAL",
      ]),
    },
    system: {
      numGpus: getNestedValue(configObj, ["SYSTEM", "NUM_GPUS"]),
      numCpus: getNestedValue(configObj, ["SYSTEM", "NUM_CPUS"]),
      parallel: getNestedValue(configObj, ["SYSTEM", "PARALLEL"]),
      distributed: getNestedValue(configObj, ["SYSTEM", "DISTRIBUTED"]),
    },
  };
};

export const summarizeConfigText = (configText, modeHint = null) => {
  const summary = {
    modeHint,
    textLength: configText?.length || 0,
    lineCount: configText ? configText.split("\n").length : 0,
  };

  if (!configText) {
    return summary;
  }

  try {
    const parsed = yaml.load(configText);
    return {
      ...summary,
      parsed: true,
      config: summarizeConfigObject(parsed, modeHint),
    };
  } catch (error) {
    return {
      ...summary,
      parsed: false,
      parseError: error.message || "Unknown YAML parse error",
    };
  }
};

export const detectConfigDiagnostics = (summary) => {
  const diagnostics = [];
  const config = summary?.config;
  if (!config) {
    return diagnostics;
  }

  if (config.dataset?.doChunkTitle && config.dataset?.usesDirectVolumePaths) {
    diagnostics.push({
      code: "tile_dataset_direct_volume_mismatch",
      severity: "warning",
      message:
        "DO_CHUNK_TITLE is enabled while IMAGE_NAME/LABEL_NAME look like direct volume files.",
    });
  }

  if (
    config.inference?.augNum !== null &&
    config.inference?.augNum !== undefined &&
    !VALID_INFERENCE_AUG_NUMS.includes(config.inference.augNum)
  ) {
    diagnostics.push({
      code: "unsupported_inference_aug_num",
      severity: "warning",
      message: `INFERENCE.AUG_NUM is ${config.inference.augNum}; supported values are ${VALID_INFERENCE_AUG_NUMS.join(", ")}.`,
    });
  }

  return diagnostics;
};
