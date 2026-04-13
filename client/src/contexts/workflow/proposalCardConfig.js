export const PROPOSAL_CARD_CONFIG = {
  prioritize_failure_hotspots: {
    title: "Prioritize Failure Hotspots",
    description:
      "Reorders the review queue around high-risk slices with the strongest failure signals.",
    keyFields: [
      ["Focus metric", "focus_metric"],
      ["Max hotspots", "max_hotspots"],
      ["Dataset split", "dataset_split"],
    ],
  },
  preview_correction_impact: {
    title: "Preview Correction Impact",
    description:
      "Estimates the downstream effect before applying a correction to the active workflow.",
    keyFields: [
      ["Target slice", "target_slice_id"],
      ["Correction mode", "correction_mode"],
      ["Estimated impact", "estimated_impact"],
    ],
  },
};

export function getProposalCardConfig(proposalType) {
  return PROPOSAL_CARD_CONFIG[proposalType] ?? null;
}

export function buildProposalSummary(proposal) {
  if (!proposal) return [];

  const config = getProposalCardConfig(proposal.type);
  if (!config) return [];

  return config.keyFields
    .map(([label, key]) => {
      const value = proposal[key];
      if (value === undefined || value === null || value === "") {
        return null;
      }
      return { label, value: String(value) };
    })
    .filter(Boolean);
}
