export const PROPOSAL_TITLES = {
  prioritize_failure_hotspots: "Prioritize Failure Hotspots",
  preview_correction_impact: "Preview Correction Impact",
};

export const PROPOSAL_FIELD_CONFIG = {
  prioritize_failure_hotspots: [
    { key: "priority_metric", label: "Priority metric" },
    { key: "max_hotspots", label: "Hotspot limit" },
    { key: "candidate_count", label: "Candidates" },
  ],
  preview_correction_impact: [
    { key: "target_region", label: "Target region" },
    { key: "estimated_quality_gain", label: "Est. quality gain" },
    { key: "confidence", label: "Confidence" },
  ],
};

export const extractKeyFields = (proposal) => {
  const fieldConfig = PROPOSAL_FIELD_CONFIG[proposal?.type] || [];
  const source = proposal?.payload || {};

  return fieldConfig
    .map(({ key, label }) => ({ label, value: source[key] }))
    .filter(({ value }) => value !== undefined && value !== null && value !== "");
};
