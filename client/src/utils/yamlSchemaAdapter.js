/**
 * yamlSchemaAdapter.js
 *
 * Detects the schema family of a parsed YAML object and translates it to the
 * flat uppercase schema required by pytorch_connectomics / yacs.
 *
 * This adapter identifies "standard" configuration schemas as defined in the
 * pytorch_connectomics core library. Both uppercase (YACS-style) and lowercase
 * (Hydra/general-style) YAML configurations are recognised generically,
 * without hardcoding any specific dataset names.
 *
 * Supported schemas:
 *  - "pytc"     : pytorch_connectomics client config  (contains pytc_version or workflow)
 *  - "standard" : pytorch_connectomics core library config, uppercase or lowercase form
 *                   Pattern A (uppercase / YACS):   ≥2 of MODEL, DATASET, SOLVER, INFERENCE, SYSTEM
 *                   Pattern B (lowercase / Hydra):  ≥2 of model, data, optimization, train, monitor
 *  - "unknown"  : does not match any known schema
 */

// ─── Schema Detection ─────────────────────────────────────────────────────────

/**
 * Top-level keys that identify a pytc client-enriched config (highest priority).
 * These fields are added by the pytc-client and are not present in plain
 * pytorch_connectomics library configs.
 */
const PYTC_KEYS = ["pytc_version", "workflow"];

/**
 * Pattern A: uppercase (YACS-style) pytorch_connectomics core keys.
 * A YAML must contain at least STANDARD_MIN_MATCH of these to be "standard".
 */
const STANDARD_KEYS_UPPER = [
  "MODEL",
  "DATASET",
  "SOLVER",
  "INFERENCE",
  "SYSTEM",
];

/**
 * Pattern B: lowercase (Hydra/general-style) pytorch_connectomics core keys.
 * A YAML must contain at least STANDARD_MIN_MATCH of these to be "standard".
 */
const STANDARD_KEYS_LOWER = [
  "model",
  "data",
  "optimization",
  "train",
  "monitor",
];

/** Minimum number of matching keys required to classify a config as "standard". */
const STANDARD_MIN_MATCH = 2;

/**
 * Returns the schema family name for the given parsed YAML object,
 * or "unknown" if it cannot be identified.
 *
 * Detection order (highest → lowest priority):
 *  1. "pytc"     — contains any key in PYTC_KEYS
 *  2. "standard" — Pattern A: ≥2 keys from STANDARD_KEYS_UPPER
 *  3. "standard" — Pattern B: ≥2 keys from STANDARD_KEYS_LOWER
 *  4. "unknown"
 *
 * @param {object} yamlData
 * @returns {"pytc"|"standard"|"unknown"}
 */
export function detectSchema(yamlData) {
  if (!yamlData || typeof yamlData !== "object") return "unknown";

  // 1. Highest priority: pytc client-enriched config
  if (PYTC_KEYS.some((k) => k in yamlData)) return "pytc";

  // 2. Pattern A — uppercase YACS-style core config
  const upperMatches = STANDARD_KEYS_UPPER.filter((k) => k in yamlData).length;
  if (upperMatches >= STANDARD_MIN_MATCH) return "standard";

  // 3. Pattern B — lowercase Hydra/general-style core config
  const lowerMatches = STANDARD_KEYS_LOWER.filter((k) => k in yamlData).length;
  if (lowerMatches >= STANDARD_MIN_MATCH) return "standard";

  return "unknown";
}

// ─── Path Helpers ─────────────────────────────────────────────────────────────

/**
 * Splits a file path into [directory, filename], handling both / and \ so the
 * adapter works correctly on Windows as well as POSIX systems.
 *
 * Examples:
 *   "datasets/train_im.h5"   → ["datasets/", "train_im.h5"]
 *   "C:\\data\\train.tif"    → ["C:\\data\\", "train.tif"]
 *   "train_im.h5"            → ["",           "train_im.h5"]
 */
function _splitPath(fullPath) {
  if (!fullPath || typeof fullPath !== "string") return ["", ""];
  const match = fullPath.match(/.*[/\\]/);
  const dir = match ? match[0] : "";
  const fileName = fullPath.slice(dir.length);
  return [dir, fileName];
}

/**
 * Maps general lowercase architecture names to pytorch_connectomics MODEL_MAP keys.
 */
function _mapArchitecture(arch) {
  const map = {
    monai_unet: "unet_3d",
    monai_basic_unet3d: "unet_3d",
    rsunet: "unet_3d",
    mednext: "unet_3d",
    unet: "unet_3d",
    unet3d: "unet_3d",
    unet2d: "unet_2d",
    fpn: "fpn_3d",
  };
  return map[(arch || "").toLowerCase()] ?? "unet_3d";
}

/**
 * Maps general lowercase scheduler names to pytorch_connectomics scheduler names.
 */
function _mapScheduler(name) {
  const map = {
    ReduceLROnPlateau: "MultiStepLR",
    reduceLROnPlateau: "MultiStepLR",
    CosineAnnealingLR: "CosineAnnealingLR",
    cosineannealinglr: "CosineAnnealingLR",
    warmupcosine: "WarmupCosineLR",
    WarmupCosineLR: "WarmupCosineLR",
  };
  return map[name] ?? "MultiStepLR";
}

/**
 * Computes a STRIDE array from a window size and overlap fraction.
 * e.g. window [112,112,112] with overlap 0.25 → stride [84,84,84]
 */
function _computeStride(windowSize, overlap) {
  const ws = windowSize ?? [112, 112, 112];
  const ov = overlap ?? 0.5;
  return ws.map((s) => Math.round(s * (1 - ov)));
}

// ─── Adapter: lowercase / Hydra-style → pytorch_connectomics uppercase ────────

/**
 * Translates a lowercase (Hydra/general) standard schema YAML object to the
 * pytorch_connectomics uppercase (YACS) schema.
 *
 * Keys that have no equivalent are preserved in a top-level `_EXTRA` object
 * so that no data is silently discarded during translation.
 *
 * @param {object} src - Parsed lowercase standard YAML object.
 * @returns {object} - Translated pytorch_connectomics schema object.
 */
function adaptStandardLower(src) {
  const out = {};

  // ── SYSTEM ──────────────────────────────────────────────────────────────
  const sys = src.system || {};
  const sysTrain = sys.training || {};
  const sysInfer = sys.inference || {};
  out.SYSTEM = {
    NUM_GPUS: sysTrain.num_gpus ?? sysInfer.num_gpus ?? 1,
    NUM_CPUS: sysTrain.num_cpus ?? sysInfer.num_cpus ?? 4,
    DISTRIBUTED: false,
    PARALLEL: "DP",
  };

  // ── MODEL ────────────────────────────────────────────────────────────────
  const mod = src.model || {};
  out.MODEL = {
    ARCHITECTURE: _mapArchitecture(mod.architecture),
    IN_PLANES: mod.in_channels ?? 1,
    OUT_PLANES: mod.out_channels ?? 1,
    INPUT_SIZE: mod.input_size ?? [112, 112, 112],
    OUTPUT_SIZE: mod.output_size ?? mod.input_size ?? [112, 112, 112],
    FILTERS: mod.filters ?? [32, 64, 128, 256],
  };
  if (mod.loss_functions) {
    out.MODEL.LOSS_OPTION = [mod.loss_functions];
    out.MODEL.LOSS_WEIGHT = [
      mod.loss_weights ?? mod.loss_functions.map(() => 1.0),
    ];
    out.MODEL.OUTPUT_ACT = [mod.loss_functions.map(() => "none")];
  }

  // ── DATASET ──────────────────────────────────────────────────────────────
  const data = src.data || {};
  const [trainInputPath, trainImageName] = _splitPath(data.train_image);
  const [, trainLabelName] = _splitPath(data.train_label);
  out.DATASET = {
    INPUT_PATH: trainInputPath || "path/to/input",
    IMAGE_NAME: trainImageName || "",
    LABEL_NAME: trainLabelName || "",
    OUTPUT_PATH: "path/to/output",
    IS_ISOTROPIC: true,
    PAD_SIZE: data.pad_size ?? [0, 0, 0],
  };

  // ── SOLVER ───────────────────────────────────────────────────────────────
  const opt = src.optimization || {};
  const optOpt = opt.optimizer || {};
  const sched = opt.scheduler || {};
  out.SOLVER = {
    NAME: optOpt.name ?? "Adam",
    BASE_LR: optOpt.lr ?? 0.001,
    WEIGHT_DECAY: optOpt.weight_decay ?? 0.0001,
    MOMENTUM: 0.9,
    BETAS: optOpt.betas ?? [0.9, 0.999],
    ITERATION_TOTAL:
      (opt.max_epochs ?? 1000) * (data.iter_num_per_epoch ?? 1000),
    SAMPLES_PER_BATCH: sysTrain.batch_size ?? 2,
    LR_SCHEDULER_NAME: _mapScheduler(sched.name),
    ITERATION_SAVE: 5000,
    ITERATION_VAL: 5000,
  };

  // ── INFERENCE ────────────────────────────────────────────────────────────
  const inf = src.inference || {};
  const infData = inf.data || {};
  const sw = inf.sliding_window || {};
  const [infInputPath, infImageName] = _splitPath(infData.test_image);
  out.INFERENCE = {
    INPUT_PATH: infInputPath || out.DATASET.INPUT_PATH,
    IMAGE_NAME: infImageName || "",
    INPUT_SIZE: sw.window_size ?? out.MODEL.INPUT_SIZE,
    OUTPUT_SIZE: sw.window_size ?? out.MODEL.OUTPUT_SIZE,
    OUTPUT_PATH: "",
    OUTPUT_NAME: "result.h5",
    SAMPLES_PER_BATCH: sysInfer.batch_size ?? 4,
    AUG_MODE: "mean",
    AUG_NUM: null,
    BLENDING: sw.blending ?? "gaussian",
    STRIDE: _computeStride(sw.window_size, sw.overlap),
  };

  // ── _EXTRA: collect all unmapped top-level keys ──────────────────────────
  // This ensures no data is lost during translation. Consumers can inspect
  // _EXTRA to find schema fields that have no pytc equivalent.
  const mappedKeys = new Set([
    "system",
    "model",
    "data",
    "optimization",
    "inference",
  ]);
  const extra = {};
  for (const [key, value] of Object.entries(src)) {
    if (!mappedKeys.has(key)) {
      extra[key] = value;
    }
  }
  if (Object.keys(extra).length > 0) {
    out._EXTRA = extra;
  }

  return out;
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Takes a parsed YAML object (any supported schema) and returns a parsed YAML
 * object conforming to the pytorch_connectomics flat uppercase (YACS) schema.
 *
 * - If the schema is "pytc" or already uppercase "standard", returns unchanged.
 * - If the schema is lowercase "standard", translates to uppercase.
 * - If the schema is unknown, returns the object unchanged with a console warn.
 *
 * @param {object} yamlData
 * @returns {{ adapted: object, originalSchema: string, wasAdapted: boolean }}
 */
export function adaptToPytcSchema(yamlData) {
  const schema = detectSchema(yamlData);

  if (schema === "pytc") {
    return { adapted: yamlData, originalSchema: "pytc", wasAdapted: false };
  }

  if (schema === "standard") {
    // Check whether this is already uppercase (Pattern A) — if so, pass through.
    const upperMatches = STANDARD_KEYS_UPPER.filter(
      (k) => k in yamlData,
    ).length;
    if (upperMatches >= STANDARD_MIN_MATCH) {
      return {
        adapted: yamlData,
        originalSchema: "standard",
        wasAdapted: false,
      };
    }
    // Pattern B: lowercase — translate to uppercase.
    const adapted = adaptStandardLower(yamlData);
    return { adapted, originalSchema: "standard", wasAdapted: true };
  }

  console.warn(
    "[yamlSchemaAdapter] Unknown YAML schema — returning as-is. " +
      "Ensure top-level keys match pytorch_connectomics conventions.",
  );
  return { adapted: yamlData, originalSchema: "unknown", wasAdapted: false };
}
