export const basename = (value) => {
  if (!value) return "";
  const trimmed = String(value).replace(/\/+$/, "");
  return trimmed.split("/").pop() || trimmed;
};

export const getProofreadingImagePath = (workflow = {}) =>
  workflow.image_path || workflow.dataset_path || "";

export const getProofreadingMaskPath = (workflow = {}) =>
  workflow.corrected_mask_path ||
  workflow.inference_output_path ||
  workflow.mask_path ||
  workflow.label_path ||
  "";

export const getProofreadingProjectName = (workflow = {}) =>
  workflow.project_name ||
  workflow.metadata?.project_name ||
  workflow.metadata?.projectName ||
  workflow.title ||
  "Proofreading review";

export const getTrainingReadyCorrectedMask = ({
  persistence = {},
  workflow = {},
} = {}) => {
  if (persistence.last_export_path) {
    return {
      path: persistence.last_export_path,
      source: "proofreading_export",
    };
  }

  if (persistence.artifact_exists && persistence.artifact_path) {
    return {
      path: persistence.artifact_path,
      source: "proofreading_persistence",
    };
  }

  if (workflow.corrected_mask_path) {
    return {
      path: workflow.corrected_mask_path,
      source: "workflow_corrected_mask",
    };
  }

  return {
    path: "",
    source: "",
  };
};
