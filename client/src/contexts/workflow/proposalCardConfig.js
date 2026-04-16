const toDisplayValue = (value) => {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
};

const compactRationale = (rationale) => {
  if (!rationale) return "No rationale provided.";
  const trimmed = String(rationale).trim();
  return trimmed.length > 160 ? `${trimmed.slice(0, 157)}…` : trimmed;
};

const pickEntries = (proposal, keys) =>
  keys
    .filter((key) => key in proposal)
    .map((key) => ({
      key,
      label: key.replace(/_/g, " "),
      value: toDisplayValue(proposal[key]),
    }));

export const getProposalCardContent = (proposal = {}) => {
  const type = proposal.type || proposal.proposal_type || proposal.action || "proposal";

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
      ]),
    };
  }

  const fallbackFields = Object.entries(proposal)
    .filter(([key]) => !["type", "proposal_type", "rationale", "why"].includes(key))
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
