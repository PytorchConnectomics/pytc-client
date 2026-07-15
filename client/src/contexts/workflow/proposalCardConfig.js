const toDisplayValue = (value) => {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  if (typeof value === "object") {
    if (value.kind) return String(value.kind);
    return "configured";
  }
  return String(value);
};

const compactPath = (value) => {
  if (!value) return "—";
  const normalized = String(value).replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 3) return normalized;
  return `.../${parts.slice(-3).join("/")}`;
};

const compactRationale = (rationale) => {
  if (!rationale) return "No rationale provided.";
  const trimmed = String(rationale).trim();
  return trimmed.length > 160 ? `${trimmed.slice(0, 157)}…` : trimmed;
};

const field = (key, label, value, options = {}) => ({
  key,
  label,
  rawValue: value,
  value:
    options.displayValue !== undefined
      ? toDisplayValue(options.displayValue)
      : toDisplayValue(value),
  editable: Boolean(options.editable),
});

const pickEntries = (proposal, keys) =>
  keys
    .filter((key) => key in proposal)
    .map((key) => ({
      key,
      label: key.replace(/_/g, " "),
      value: toDisplayValue(proposal[key]),
    }));

const CLIENT_EFFECT_FIELD_SPECS = [
  ["set_training_config_preset", "Config", "config_preset"],
  ["set_training_image_path", "Images", "image_path"],
  ["set_training_label_path", "Labels", "label_path"],
  ["set_training_output_path", "Output", "output_path"],
  ["set_training_log_path", "Log", "log_path"],
  ["set_inference_config_preset", "Config", "inference_config_preset"],
  ["set_inference_checkpoint_path", "Checkpoint", "checkpoint_path"],
  ["set_inference_image_path", "Image", "inference_image_path"],
  ["set_inference_label_path", "Label", "inference_label_path"],
  ["set_inference_output_path", "Output", "inference_output_path"],
  ["set_visualization_image_path", "Image", "visualization_image_path"],
  ["set_visualization_label_path", "Label", "visualization_label_path"],
  ["set_visualization_scales", "Scales", "visualization_scales"],
  ["set_proofreading_dataset_path", "Image", "proofreading_dataset_path"],
  ["set_proofreading_mask_path", "Mask", "proofreading_mask_path"],
  ["set_proofreading_project_name", "Project", "proofreading_project_name"],
];

const clientEffectFields = (clientEffects = {}) => {
  if (!clientEffects || typeof clientEffects !== "object") return [];
  return CLIENT_EFFECT_FIELD_SPECS.filter(
    ([effectKey]) => clientEffects[effectKey] !== undefined,
  ).map(([effectKey, label, overrideKey]) => {
    const rawValue = clientEffects[effectKey];
    const shouldCompact =
      typeof rawValue === "string" &&
      (rawValue.includes("/") || rawValue.includes("\\"));
    return field(overrideKey, label, rawValue, {
      editable: true,
      displayValue: shouldCompact ? compactPath(rawValue) : rawValue,
    });
  });
};

const trainingSubsetFields = (subset = {}) => {
  if (!subset || typeof subset !== "object") return [];
  const statuses = Array.isArray(subset.training_statuses)
    ? subset.training_statuses
    : [];
  const source =
    statuses.length === 1 && statuses[0] === "ground_truth"
      ? "fully good GT"
      : statuses.join(", ") || "selected labels";
  const fields = [];
  if (subset.train_volume_count !== undefined) {
    fields.push(
      field(
        "training_subset_train",
        "Training set",
        `${subset.train_volume_count} ${source} volume${
          Number(subset.train_volume_count) === 1 ? "" : "s"
        }`,
      ),
    );
  }
  if (subset.target_volume_count !== undefined) {
    fields.push(
      field(
        "training_subset_targets",
        "After training",
        `${subset.target_volume_count} image-only target${
          Number(subset.target_volume_count) === 1 ? "" : "s"
        }`,
      ),
    );
  }
  if (subset.review_volume_count) {
    fields.push(
      field(
        "training_subset_review",
        "Left out",
        `${subset.review_volume_count} draft mask${
          Number(subset.review_volume_count) === 1 ? "" : "s"
        }`,
      ),
    );
  }
  if (subset.manifest_path) {
    fields.push(
      field(
        "training_subset_manifest",
        "Manifest",
        compactPath(subset.manifest_path),
      ),
    );
  }
  return fields;
};

export const getProposalCardContent = (proposal = {}) => {
  const type =
    proposal.type || proposal.proposal_type || proposal.action || "proposal";

  if (type === "prioritize_failure_hotspots") {
    return {
      type,
      title: "Prioritize Failure Hotspots",
      rationale: compactRationale(proposal.rationale || proposal.why),
      fields: pickEntries(proposal, [
        "target_dataset",
        "hotspots",
        "priority_metric",
        "min_failure_rate",
      ]),
    };
  }

  if (type === "preview_correction_impact") {
    return {
      type,
      title: "Preview Correction Impact",
      rationale: compactRationale(proposal.rationale || proposal.why),
      fields: pickEntries(proposal, [
        "target_metric",
        "expected_delta",
        "sample_size",
        "confidence",
      ]),
    };
  }

  if (type === "stage_retraining_from_corrections") {
    return {
      type,
      title: "Stage Retraining From Corrections",
      rationale: compactRationale(
        proposal.rationale ||
          proposal.why ||
          "Stage corrected masks for the next model iteration.",
      ),
      fields: pickEntries(proposal, [
        "corrected_mask_path",
        "written_path",
        "training_output_path",
      ]).map((item) =>
        [
          "corrected_mask_path",
          "written_path",
          "training_output_path",
        ].includes(item.key)
          ? {
              ...item,
              rawValue: proposal[item.key],
              value: compactPath(proposal[item.key]),
              editable: true,
            }
          : item,
      ),
    };
  }

  if (type === "start_training_run") {
    const subset = proposal.training_volume_subset;
    return {
      type,
      title: "Approve Training Run",
      rationale: compactRationale(
        proposal.rationale ||
          proposal.why ||
          "Start training with the proposed inputs and safe defaults.",
      ),
      fields: [
        field("config_preset", "Config", proposal.config_preset, {
          editable: true,
          displayValue: compactPath(proposal.config_preset),
        }),
        field("image_path", "Images", proposal.image_path, {
          editable: true,
          displayValue: compactPath(proposal.image_path),
        }),
        field("label_path", "Labels", proposal.label_path, {
          editable: true,
          displayValue: compactPath(proposal.label_path),
        }),
        field("output_path", "Output", proposal.output_path, {
          editable: true,
          displayValue: compactPath(proposal.output_path),
        }),
        ...trainingSubsetFields(subset),
        field(
          "parameters",
          "Parameters",
          proposal.autopick_parameters
            ? "safe defaults"
            : proposal.parameter_mode,
          { editable: false },
        ),
      ].filter((item) => item.value !== "—"),
    };
  }

  if (type === "run_client_effects") {
    return {
      type,
      title: "Approve App Action",
      rationale: compactRationale(
        proposal.rationale ||
          proposal.why ||
          "Run the proposed assistant action inside the app.",
      ),
      fields: pickEntries(proposal, [
        "item_label",
        "item_type",
        "risk_level",
        "runtime_action",
        "workflow_action",
      ]).concat(clientEffectFields(proposal.client_effects)),
    };
  }

  const fallbackFields = Object.entries(proposal)
    .filter(
      ([key]) => !["type", "proposal_type", "rationale", "why"].includes(key),
    )
    .slice(0, 4)
    .map(([key, value]) => ({
      key,
      label: key.replace(/_/g, " "),
      value: toDisplayValue(value),
    }));

  return {
    type,
    title: "Agent Proposal",
    rationale: compactRationale(proposal.rationale || proposal.why),
    fields: fallbackFields,
  };
};
