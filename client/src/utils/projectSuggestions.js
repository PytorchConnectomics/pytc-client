export const PROJECT_ROLE_LABELS = {
  image: "image",
  label: "label",
  prediction: "prediction",
  config: "config",
  checkpoint: "checkpoint",
  volume: "other volume",
};

export const joinProjectPath = (rootPath, relativePath) => {
  if (!rootPath || !relativePath) return "";
  return `${String(rootPath).replace(/\/+$/, "")}/${String(relativePath).replace(/^\/+/, "")}`;
};

const isAbsoluteOrUriPath = (path) =>
  /^([a-z]+:)?\/\//i.test(String(path || "")) ||
  String(path || "").startsWith("/");

export const normalizeProjectRolePath = (rootPath, rolePath) => {
  if (!rolePath) return "";
  return isAbsoluteOrUriPath(rolePath)
    ? String(rolePath)
    : joinProjectPath(rootPath, rolePath);
};

export const getProjectVolumeSetsFromSuggestion = (suggestion) => {
  const profile = suggestion?.profile || {};
  return profile.volume_sets || profile.schema?.volume_sets || [];
};

export const getProjectContextDefaultsFromSuggestion = (suggestion) => {
  const profile = suggestion?.profile || {};
  const volumeSets = getProjectVolumeSetsFromSuggestion(suggestion);
  const counts = profile.counts || {};
  const contentHints =
    profile.context_hints || profile.schema?.context_hints || {};
  const defaults = {};

  [
    "imaging_modality",
    "target_structure",
    "task_goal",
    "optimization_priority",
    "label_status",
  ].forEach((key) => {
    if (contentHints[key]) {
      defaults[key] = contentHints[key];
    }
  });

  const volumeSetNames = volumeSets.map((set) =>
    String(set.name || "").toLowerCase(),
  );
  if (
    volumeSetNames.some((name) => /train/.test(name)) &&
    volumeSetNames.some((name) => /(val|valid|test)/.test(name))
  ) {
    defaults.data_unit = "train/validation/test folders";
  } else if (volumeSets.length > 1 || Number(counts.image || 0) > 1) {
    defaults.data_unit = "folder of volumes";
  } else if (Number(counts.image || 0) === 1) {
    defaults.data_unit = "single volume";
  }

  if (!defaults.task_goal) {
    defaults.task_goal = "segmentation";
  }
  if (!defaults.optimization_priority) {
    defaults.optimization_priority = "accuracy";
  }

  return defaults;
};

export const inferProjectContextFromDescription = (description) => {
  const text = String(description || "").trim();
  if (!text) return null;

  const lower = text.toLowerCase();
  const normalizedLower = lower.replace(/[^a-z0-9+-]+/g, " ");
  const paddedLower = ` ${normalizedLower} `;
  const context = {
    freeform_note: text.slice(0, 1000),
  };

  const modalityTerms = [
    ["electron microscopy", ["electron microscopy", "electron microscope"]],
    ["EM", [" em ", "sem", "tem", "fib-sem", "fib sem"]],
    ["confocal microscopy", ["confocal"]],
    ["light-sheet microscopy", ["light sheet", "light-sheet"]],
    ["fluorescence microscopy", ["fluorescence", "fluorescent"]],
    ["brightfield microscopy", ["brightfield", "bright-field"]],
    ["MRI", [" mri ", "mri"]],
    ["CT", [" ct ", "micro-ct", "micro ct"]],
  ];

  const modality = modalityTerms.find(([, terms]) =>
    terms.some((term) => paddedLower.includes(term)),
  );
  if (modality) {
    context.imaging_modality = modality[0];
  }

  const targetTerms = [
    ["mitochondria", ["mitochondria", "mitochondrion", "mito"]],
    ["membranes", ["membrane", "membranes"]],
    ["synapses", ["synapse", "synapses"]],
    ["nuclei", ["nucleus", "nuclei"]],
    ["cells", ["cell", "cells"]],
    ["neurites", ["neurite", "neurites", "axon", "dendrite"]],
    ["vasculature", ["vessel", "vasculature", "blood vessel"]],
    ["organelle", ["organelle", "organelles"]],
  ];

  const target = targetTerms.find(([, terms]) =>
    terms.some((term) => lower.includes(term)),
  );
  if (target) {
    context.target_structure = target[0];
  }

  if (/(fast|quick|smoke|prototype|rough|draft)/.test(lower)) {
    context.optimization_priority = "speed";
  } else if (/(accurate|accuracy|quality|best|careful|final)/.test(lower)) {
    context.optimization_priority = "accuracy";
  }

  if (/(proofread|review|correct|fix|curat)/.test(lower)) {
    context.task_goal = "proofreading";
  } else if (/(segment|segmentation|infer|inference|predict)/.test(lower)) {
    context.task_goal = "segmentation";
  } else if (/(retrain|fine.?tune|\btrain(?:ing)?\b(?!\s*\/\s*val))/.test(lower)) {
    context.task_goal = "training";
  } else if (/(compare|metric|evaluate|evaluation|before.*after)/.test(lower)) {
    context.task_goal = "comparison";
  }

  if (/(train|val|valid|test)\s*(\/|and|,|\+)\s*(val|valid|test|train)/.test(lower)) {
    context.data_unit = "train/validation/test folders";
  } else if (/(folder|directory|batch|multiple|several|many|set of|collection)/.test(lower)) {
    context.data_unit = "folder of volumes";
  } else if (/(one|single)\s+(volume|image|stack|file)/.test(lower)) {
    context.data_unit = "single volume";
  } else if (/(tile|tiles|crop|crops|patch|patches)/.test(lower)) {
    context.data_unit = "tiles or crops";
  } else if (/(time.?series|timeseries|movie|frames)/.test(lower)) {
    context.data_unit = "time series";
  }

  if (/(no labels|unlabeled|no mask|without labels|raw only)/.test(lower)) {
    context.label_status = "no labels";
  } else if (/(rough|weak|partial|imperfect).*(label|mask|seg)/.test(lower)) {
    context.label_status = "rough labels";
  } else if (/(expert|manual|ground truth|ground-truth|gt).*(label|mask|seg)/.test(lower)) {
    context.label_status = "expert labels";
  } else if (/(prediction|predictions|model output|baseline).*(mask|seg|available|exist)/.test(lower)) {
    context.label_status = "predictions available";
  }

  return context;
};

const PROJECT_CONTEXT_REQUIRED_FIELDS = [
  {
    key: "imaging_modality",
    label: "imaging modality",
    question: "What imaging modality is this from, such as EM, fluorescence, or micro-CT?",
  },
  {
    key: "target_structure",
    label: "target structure",
    question: "What structure should be segmented or proofread?",
  },
  {
    key: "task_goal",
    label: "task goal",
    question: "Is the immediate goal segmentation, proofreading, training, or comparison?",
  },
  {
    key: "data_unit",
    label: "data organization",
    question: "Is this one volume, a folder of volumes, train/val/test splits, tiles, or a time series?",
  },
  {
    key: "optimization_priority",
    label: "speed vs accuracy preference",
    question: "Should I prioritize speed or accuracy for this project?",
  },
];

export const evaluateProjectContextCompleteness = (
  description,
  options = {},
) => {
  const context = {
    ...(options.defaultContext && typeof options.defaultContext === "object"
      ? options.defaultContext
      : {}),
    ...(inferProjectContextFromDescription(description) || {}),
  };
  if (options.useDefaults) {
    return {
      complete: true,
      context: {
        ...context,
        use_defaults: true,
      },
      missing: [],
      known: context,
      next_question: "",
    };
  }

  const missingFields = PROJECT_CONTEXT_REQUIRED_FIELDS.filter(
    (field) => !context[field.key],
  );
  const nextQuestion = missingFields[0]?.question || "";
  return {
    complete: missingFields.length === 0,
    context,
    known: Object.fromEntries(
      Object.entries(context).filter(([, value]) => Boolean(value)),
    ),
    missing: missingFields.map((field) => field.label),
    next_question: nextQuestion,
  };
};

export const describeProjectContextAssessment = (assessment) => {
  if (!assessment) {
    return "Describe the dataset so I can choose sensible workflow defaults.";
  }
  if (assessment.complete) {
    return "I have enough project context to continue.";
  }
  return assessment.next_question || "Tell me one more detail about this dataset.";
};

const preferDirectoryDefault = (profile, role) => {
  const counts = profile.counts || {};
  const primaryPaths = profile.schema?.primary_paths || {};
  const volumeSets = profile.volume_sets || profile.schema?.volume_sets || [];

  if (role === "image" && counts.image > 1 && volumeSets[0]?.image_root) {
    return volumeSets[0].image_root;
  }
  if (
    (role === "label" || role === "mask") &&
    counts.label > 1 &&
    volumeSets[0]?.label_root
  ) {
    return volumeSets[0].label_root;
  }
  if (counts[role] > 1 && primaryPaths[`${role}_root`]) {
    return primaryPaths[`${role}_root`];
  }
  return "";
};

export const getProjectRoleDefaultsFromSuggestion = (suggestion) => {
  const profile = suggestion?.profile || {};
  const primaryPaths = profile.schema?.primary_paths || {};
  const examples = profile.examples || {};
  const paired = profile.paired_examples?.[0] || {};
  const rootPath = suggestion?.directory_path;
  const imageRelative =
    preferDirectoryDefault(profile, "image") ||
    primaryPaths.image || paired.image || examples.image?.[0] || examples.volume?.[0];
  const labelRelative =
    preferDirectoryDefault(profile, "label") ||
    primaryPaths.label || primaryPaths.mask || paired.label || examples.label?.[0];
  const predictionRelative =
    preferDirectoryDefault(profile, "prediction") ||
    primaryPaths.prediction ||
    examples.prediction?.[0];
  const checkpointRelative = primaryPaths.checkpoint || examples.checkpoint?.[0];
  const configRelative = primaryPaths.config || examples.config?.[0];

  return {
    image: normalizeProjectRolePath(rootPath, imageRelative),
    label: normalizeProjectRolePath(rootPath, labelRelative),
    prediction: normalizeProjectRolePath(rootPath, predictionRelative),
    checkpoint: normalizeProjectRolePath(rootPath, checkpointRelative),
    config: normalizeProjectRolePath(rootPath, configRelative),
  };
};

export const buildWorkflowPatchFromConfirmedProjectRoles = ({
  rootPath,
  roles = {},
} = {}) => {
  const labelOrMask = roles.label || roles.mask || "";
  const patch = {
    dataset_path: rootPath || null,
    image_path: normalizeProjectRolePath(rootPath, roles.image) || null,
    label_path: normalizeProjectRolePath(rootPath, labelOrMask) || null,
    mask_path: normalizeProjectRolePath(rootPath, roles.mask || labelOrMask) || null,
    inference_output_path:
      normalizeProjectRolePath(rootPath, roles.prediction) || null,
    checkpoint_path: normalizeProjectRolePath(rootPath, roles.checkpoint) || null,
    config_path: normalizeProjectRolePath(rootPath, roles.config) || null,
  };
  return Object.fromEntries(
    Object.entries(patch).filter(([, value]) => Boolean(value)),
  );
};

export const buildWorkflowPatchFromProjectSuggestion = (suggestion) => {
  const rootPath = suggestion?.directory_path;
  return buildWorkflowPatchFromConfirmedProjectRoles({
    rootPath,
    roles: getProjectRoleDefaultsFromSuggestion(suggestion),
  });
};

export const summarizeProjectSuggestionForWorkflow = (
  suggestion,
  overrides = {},
) => {
  const profile = suggestion?.profile || {};
  const pairedExample = profile.paired_examples?.[0] || null;
  return {
    id: suggestion?.id || null,
    name: suggestion?.name || null,
    directory_path: suggestion?.directory_path || null,
    already_mounted: Boolean(suggestion?.already_mounted),
    mounted_root_id: suggestion?.mounted_root_id || null,
    recommended: Boolean(suggestion?.recommended),
    profile: {
      ready_for_smoke: Boolean(profile.ready_for_smoke),
      schema: profile.schema || null,
      counts: profile.counts || {},
      missing_roles: profile.missing_roles || [],
      paired_example: pairedExample,
      role_directories: profile.role_directories || profile.schema?.role_directories || {},
      volume_sets: getProjectVolumeSetsFromSuggestion(suggestion),
    },
    inferred_paths: buildWorkflowPatchFromProjectSuggestion(suggestion),
    ...overrides,
  };
};

const tokenizeGoal = (goal) =>
  String(goal || "")
    .toLowerCase()
    .split(/[^a-z0-9_.-]+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2);

const flattenSuggestionText = (suggestion) => {
  const profile = suggestion?.profile || {};
  const examples = profile.examples || {};
  const pairedExamples = profile.paired_examples || [];
  return [
    suggestion?.id,
    suggestion?.name,
    suggestion?.directory_path,
    suggestion?.description,
    ...Object.values(examples).flat(),
    ...pairedExamples.flatMap((pair) => [pair?.image, pair?.label]),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
};

export const scoreProjectSuggestionForGoal = (suggestion, goal) => {
  const tokens = tokenizeGoal(goal);
  const profile = suggestion?.profile || {};
  const counts = profile.counts || {};
  const haystack = flattenSuggestionText(suggestion);

  if (tokens.length === 0) {
    return {
      score: suggestion?.recommended ? 10 : 0,
      reason: suggestion?.recommended ? "recommended" : "",
    };
  }

  let score = 0;
  const reasons = [];
  tokens.forEach((token) => {
    if (haystack.includes(token)) {
      score += 8;
      reasons.push(token);
    }
  });

  const goalText = tokens.join(" ");
  const hasImageLabel = counts.image > 0 && counts.label > 0;
  const hasLoopArtifacts =
    counts.image > 0 &&
    counts.label > 0 &&
    counts.prediction > 0 &&
    counts.checkpoint > 0;

  if (/(proofread|review|correct|fix|mask|label)/.test(goalText) && hasImageLabel) {
    score += 3;
    reasons.push("image/mask pair");
  }
  if (/(segment|segmentation|predict|prediction|infer|inference)/.test(goalText)) {
    if (counts.prediction > 0) {
      score += 3;
      reasons.push("prediction artifacts");
    } else if (counts.image > 0) {
      score += 2;
      reasons.push("image data");
    }
  }
  if (/mitochond/.test(goalText) && haystack.includes("mito")) {
    score += 7;
    reasons.push("mitochondria");
  }
  if (/(train|retrain|compare|metric|baseline|candidate|closed|loop)/.test(goalText)) {
    if (hasLoopArtifacts) {
      score += 6;
      reasons.push("loop artifacts");
    } else if (hasImageLabel) {
      score += 2;
      reasons.push("trainable pair");
    }
  }
  if (/(tif|tiff)/.test(goalText) && /\.(ome\.)?tiff?\b/.test(haystack)) {
    score += 5;
    reasons.push("TIFF data");
  }
  if (/(h5|hdf5)/.test(goalText) && /\.(h5|hdf5)\b/.test(haystack)) {
    score += 5;
    reasons.push("HDF5 data");
  }
  if (suggestion?.recommended && score > 0) {
    score += 1;
  }

  return {
    score,
    reason: reasons.slice(0, 3).join(", "),
  };
};

export const rankProjectSuggestionsForGoal = (suggestions, goal) =>
  (suggestions || [])
    .map((suggestion, originalIndex) => ({
      ...suggestion,
      match: scoreProjectSuggestionForGoal(suggestion, goal),
      originalIndex,
    }))
    .sort((a, b) => {
      if (b.match.score !== a.match.score) {
        return b.match.score - a.match.score;
      }
      if (Boolean(b.recommended) !== Boolean(a.recommended)) {
        return b.recommended ? 1 : -1;
      }
      return a.originalIndex - b.originalIndex;
    });

export const selectSuggestedProjectIdsForGoal = (suggestions, goal) => {
  const ranked = rankProjectSuggestionsForGoal(suggestions, goal);
  if (!ranked.length) return new Set();
  if (tokenizeGoal(goal).length === 0) {
    const recommended = ranked.find((suggestion) => suggestion.recommended);
    return new Set([(recommended || ranked[0]).id]);
  }
  return ranked[0].match.score > 0 ? new Set([ranked[0].id]) : new Set();
};
