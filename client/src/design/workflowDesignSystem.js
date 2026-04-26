export const antdWorkflowTheme = {
  token: {
    colorPrimary: "#3f37c9",
    colorInfo: "#3f37c9",
    colorSuccess: "#2f7d32",
    colorWarning: "#b8660f",
    colorError: "#b13a2f",
    borderRadius: 8,
    fontFamily:
      '"IBM Plex Sans", "Aptos", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif',
    fontFamilyCode:
      '"IBM Plex Mono", "SFMono-Regular", Menlo, Monaco, Consolas, monospace',
  },
};

export const STAGE_META = {
  setup: {
    label: "Setup",
    tone: "neutral",
    color: "default",
    description: "Define project context and source artifacts.",
  },
  visualization: {
    label: "Visualization",
    tone: "teal",
    color: "cyan",
    description: "Inspect source image and labels.",
  },
  inference: {
    label: "Inference",
    tone: "blue",
    color: "blue",
    description: "Run model prediction and inspect output.",
  },
  proofreading: {
    label: "Proofreading",
    tone: "amber",
    color: "gold",
    description: "Correct masks and classify failure regions.",
  },
  retraining_staged: {
    label: "Retraining Staged",
    tone: "orange",
    color: "orange",
    description: "Corrections are linked to the next training run.",
  },
  evaluation: {
    label: "Evaluation",
    tone: "green",
    color: "green",
    description: "Compare before/after model behavior.",
  },
};

export const SEVERITY_META = {
  low: { label: "Low", color: "default", tone: "neutral" },
  medium: { label: "Medium", color: "orange", tone: "amber" },
  high: { label: "High", color: "red", tone: "red" },
};

export const APPROVAL_META = {
  not_required: { label: "Logged", color: "default", tone: "neutral" },
  pending: { label: "Needs Review", color: "gold", tone: "amber" },
  approved: { label: "Approved", color: "green", tone: "green" },
  rejected: { label: "Rejected", color: "red", tone: "red" },
};

export const ARTIFACT_META = {
  dataset: { label: "Dataset", color: "blue" },
  image_volume: { label: "Image", color: "cyan" },
  label_volume: { label: "Label", color: "geekblue" },
  mask_volume: { label: "Mask", color: "purple" },
  correction_set: { label: "CorrectionSet", color: "gold" },
  model_checkpoint: { label: "Checkpoint", color: "green" },
  training_output: { label: "Training Run", color: "lime" },
  inference_output: { label: "Prediction", color: "blue" },
  evaluation_report: { label: "Evaluation", color: "volcano" },
  evidence_bundle: { label: "Evidence Bundle", color: "magenta" },
};

export function getStageMeta(stage) {
  return STAGE_META[stage] || {
    label: stage || "No Workflow",
    tone: "neutral",
    color: "default",
    description: "No active workflow stage.",
  };
}

export function getSeverityMeta(severity) {
  return SEVERITY_META[severity] || SEVERITY_META.low;
}

export function getApprovalMeta(status) {
  return APPROVAL_META[status] || APPROVAL_META.not_required;
}

export function getArtifactMeta(type) {
  return ARTIFACT_META[type] || {
    label: type || "Artifact",
    color: "default",
  };
}
