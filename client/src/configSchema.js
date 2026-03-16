const LEGACY_ROOT_KEYS = ["DATASET", "SOLVER", "SYSTEM", "INFERENCE", "MODEL"];
const V2_ROOT_KEYS = [
  "model",
  "data",
  "train",
  "test",
  "monitor",
  "inference",
  "optimization",
  "default",
];

const SLIDER_PATHS = {
  training: {
    batch_size: [
      ["SOLVER", "SAMPLES_PER_BATCH"],
      ["data", "dataloader", "batch_size"],
      ["default", "data", "dataloader", "batch_size"],
    ],
    gpus: [
      ["SYSTEM", "NUM_GPUS"],
      ["train", "system", "num_gpus"],
      ["system", "num_gpus"],
      ["default", "system", "num_gpus"],
    ],
    cpus: [
      ["SYSTEM", "NUM_CPUS"],
      ["train", "system", "num_workers"],
      ["system", "num_workers"],
      ["default", "system", "num_workers"],
    ],
  },
  inference: {
    batch_size: [
      ["INFERENCE", "SAMPLES_PER_BATCH"],
      ["inference", "batch_size"],
      ["default", "inference", "batch_size"],
    ],
    augmentations: [["INFERENCE", "AUG_NUM"]],
  },
};

function isObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function joinPath(basePath, leaf) {
  if (!basePath) return leaf;
  return basePath.endsWith("/") ? `${basePath}${leaf}` : `${basePath}/${leaf}`;
}

export function getPathValue(data, path) {
  if (!isObject(data) || !Array.isArray(path)) return undefined;
  return path.reduce((cursor, key) => {
    if (!isObject(cursor) || !(key in cursor)) return undefined;
    return cursor[key];
  }, data);
}

export function hasPath(data, path) {
  return getPathValue(data, path) !== undefined;
}

export function setPathValue(data, path, value) {
  if (!isObject(data) || !Array.isArray(path) || path.length === 0) return;
  let cursor = data;
  path.forEach((key, index) => {
    if (index === path.length - 1) {
      cursor[key] = value;
      return;
    }
    if (!isObject(cursor[key])) {
      cursor[key] = {};
    }
    cursor = cursor[key];
  });
}

export function pickFirstExistingPath(data, candidates) {
  if (!Array.isArray(candidates)) return null;
  for (const candidate of candidates) {
    if (hasPath(data, candidate)) return candidate;
  }
  return null;
}

export function detectConfigSchema(configObj) {
  if (!isObject(configObj)) return "unknown";
  const legacyScore = LEGACY_ROOT_KEYS.filter((k) => k in configObj).length;
  const v2Score = V2_ROOT_KEYS.filter((k) => k in configObj).length;
  if (legacyScore === 0 && v2Score === 0) return "unknown";
  return legacyScore >= v2Score ? "legacy" : "v2";
}

function resolveSliderPath(configObj, type, key) {
  const candidates = SLIDER_PATHS[type]?.[key] || [];
  return pickFirstExistingPath(configObj, candidates);
}

export function getSliderValue(configObj, type, key) {
  const path = resolveSliderPath(configObj, type, key);
  return path ? getPathValue(configObj, path) : undefined;
}

export function isSliderSupported(configObj, type, key) {
  return Boolean(resolveSliderPath(configObj, type, key));
}

export function setSliderValue(configObj, type, key, value) {
  const path = resolveSliderPath(configObj, type, key);
  if (!path) return false;
  setPathValue(configObj, path, value);
  return true;
}

export function setTrainingOutputPath(configObj, outputPath) {
  if (!outputPath || !isObject(configObj)) return;
  const schema = detectConfigSchema(configObj);
  if (schema === "legacy") {
    setPathValue(configObj, ["DATASET", "OUTPUT_PATH"], outputPath);
    return;
  }
  const checkpointsPath = joinPath(outputPath, "checkpoints");
  if (hasPath(configObj, ["train", "monitor", "checkpoint", "dirpath"])) {
    setPathValue(configObj, ["train", "monitor", "checkpoint", "dirpath"], checkpointsPath);
    return;
  }
  if (hasPath(configObj, ["monitor", "checkpoint", "dirpath"])) {
    setPathValue(configObj, ["monitor", "checkpoint", "dirpath"], checkpointsPath);
    return;
  }
  setPathValue(configObj, ["monitor", "checkpoint", "dirpath"], checkpointsPath);
}

export function setInferenceOutputPath(configObj, outputPath) {
  if (!outputPath || !isObject(configObj)) return;
  const schema = detectConfigSchema(configObj);
  if (schema === "legacy") {
    setPathValue(configObj, ["INFERENCE", "OUTPUT_PATH"], outputPath);
    return;
  }
  setPathValue(configObj, ["inference", "save_prediction", "output_path"], outputPath);
}

export function setInferenceExecutionDefaults(configObj) {
  if (!isObject(configObj)) return;
  const schema = detectConfigSchema(configObj);
  if (schema === "legacy") {
    setPathValue(configObj, ["SYSTEM", "NUM_GPUS"], 1);
    return;
  }
  const existingPath = pickFirstExistingPath(configObj, [
    ["test", "system", "num_gpus"],
    ["system", "num_gpus"],
    ["default", "system", "num_gpus"],
  ]);
  if (existingPath) {
    setPathValue(configObj, existingPath, 1);
    return;
  }
  setPathValue(configObj, ["system", "num_gpus"], 1);
}

export function applyInputPaths(
  configObj,
  { mode, inputImagePath, inputLabelPath, inputPath, outputPath },
) {
  if (!isObject(configObj) || !inputImagePath || !inputLabelPath) return;
  const schema = detectConfigSchema(configObj);

  if (schema === "legacy") {
    setPathValue(configObj, ["DATASET", "INPUT_PATH"], inputPath);
    setPathValue(
      configObj,
      ["DATASET", "IMAGE_NAME"],
      inputImagePath.replace(inputPath, ""),
    );
    setPathValue(
      configObj,
      ["DATASET", "LABEL_NAME"],
      inputLabelPath.replace(inputPath, ""),
    );
    if (outputPath) {
      if (mode === "training") {
        setTrainingOutputPath(configObj, outputPath);
      } else {
        setInferenceOutputPath(configObj, outputPath);
      }
    }
    return;
  }

  if (mode === "training") {
    const imagePath =
      pickFirstExistingPath(configObj, [
        ["train", "data", "train", "image"],
        ["data", "train", "image"],
      ]) || ["train", "data", "train", "image"];
    const labelPath =
      pickFirstExistingPath(configObj, [
        ["train", "data", "train", "label"],
        ["data", "train", "label"],
      ]) || ["train", "data", "train", "label"];
    setPathValue(configObj, imagePath, inputImagePath);
    setPathValue(configObj, labelPath, inputLabelPath);
    if (outputPath) {
      setTrainingOutputPath(configObj, outputPath);
    }
    return;
  }

  const imagePath =
    pickFirstExistingPath(configObj, [
      ["test", "data", "test", "image"],
      ["data", "test", "image"],
    ]) || ["test", "data", "test", "image"];
  const labelPath =
    pickFirstExistingPath(configObj, [
      ["test", "data", "test", "label"],
      ["data", "test", "label"],
    ]) || ["test", "data", "test", "label"];
  setPathValue(configObj, imagePath, inputImagePath);
  setPathValue(configObj, labelPath, inputLabelPath);
  if (outputPath) {
    setInferenceOutputPath(configObj, outputPath);
  }
}

export function getArchitectureValue(configObj) {
  if (!isObject(configObj)) return undefined;
  const path = pickFirstExistingPath(configObj, [
    ["MODEL", "ARCHITECTURE"],
    ["model", "arch", "type"],
    ["default", "model", "arch", "profile"],
  ]);
  return path ? getPathValue(configObj, path) : undefined;
}

export function isArchitectureSupported(configObj) {
  if (!isObject(configObj)) return false;
  return Boolean(
    pickFirstExistingPath(configObj, [
      ["MODEL", "ARCHITECTURE"],
      ["model", "arch", "type"],
      ["default", "model", "arch", "profile"],
    ]),
  );
}

export function setArchitectureValue(configObj, value) {
  if (!isObject(configObj)) return false;
  const existingPath = pickFirstExistingPath(configObj, [
    ["MODEL", "ARCHITECTURE"],
    ["model", "arch", "type"],
    ["default", "model", "arch", "profile"],
  ]);
  if (existingPath) {
    setPathValue(configObj, existingPath, value);
    return true;
  }
  return false;
}
