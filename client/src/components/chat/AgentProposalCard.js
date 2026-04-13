import React from "react";
import {
  extractKeyFields,
  PROPOSAL_TITLES,
} from "../../contexts/workflow/proposalCardFields";

const cardStyle = {
  border: "1px solid #d9d9d9",
  borderRadius: 8,
  padding: 10,
  marginTop: 8,
};

const rationaleStyle = {
  margin: "6px 0 8px",
  color: "#595959",
  fontSize: 13,
};

function ProposalCardBody({ proposal }) {
  if (
    proposal?.type !== "prioritize_failure_hotspots" &&
    proposal?.type !== "preview_correction_impact"
  ) {
    return null;
  }

  const keyFields = extractKeyFields(proposal);
  const rationale = proposal?.rationale || proposal?.summary || "No rationale provided.";

  return (
    <>
      <strong>{PROPOSAL_TITLES[proposal.type]}</strong>
      <div style={rationaleStyle}>{rationale}</div>
      {keyFields.length > 0 ? (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {keyFields.map((field) => (
            <li key={field.label}>
              <strong>{field.label}:</strong> {String(field.value)}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

export default function AgentProposalCard({
  proposal,
  onApprove,
  onReject,
  renderFallback,
}) {
  const isNewProposalType =
    proposal?.type === "prioritize_failure_hotspots" ||
    proposal?.type === "preview_correction_impact";

  if (!isNewProposalType) {
    return renderFallback ? renderFallback(proposal) : null;
  }

  return (
    <div data-testid={`proposal-card-${proposal.type}`} style={cardStyle}>
      <ProposalCardBody proposal={proposal} />
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button type="button" onClick={() => onApprove?.(proposal)}>
          Approve
        </button>
        <button type="button" onClick={() => onReject?.(proposal)}>
          Reject
        </button>
      </div>
    </div>
  );
}
