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

export const getProjectRoleDefaultsFromSuggestion = (suggestion) => {
  const profile = suggestion?.profile || {};
  const primaryPaths = profile.schema?.primary_paths || {};
  const examples = profile.examples || {};
  const paired = profile.paired_examples?.[0] || {};
  const rootPath = suggestion?.directory_path;
  const imageRelative =
    primaryPaths.image || paired.image || examples.image?.[0] || examples.volume?.[0];
  const labelRelative =
    primaryPaths.label || primaryPaths.mask || paired.label || examples.label?.[0];
  const predictionRelative = primaryPaths.prediction || examples.prediction?.[0];
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
