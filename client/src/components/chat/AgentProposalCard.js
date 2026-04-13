import React from "react";
import { getProposalCardContent } from "../../contexts/workflow/proposalCardConfig";

function AgentProposalCard({ proposal, onApprove, onReject, disabled = false }) {
  const content = getProposalCardContent(proposal);

  return (
    <section
      aria-label={`proposal-${content.type}`}
      style={{
        border: "1px solid #d9d9d9",
        borderRadius: 8,
        padding: 12,
        background: "#fff",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>{content.title}</div>
      <div style={{ marginBottom: 8, fontSize: 13 }}>{content.rationale}</div>
      <dl
        style={{
          margin: 0,
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          columnGap: 8,
          rowGap: 4,
          fontSize: 12,
        }}
      >
        {content.fields.map((field) => (
          <React.Fragment key={field.key}>
            <dt style={{ textTransform: "capitalize", color: "#666" }}>{field.label}</dt>
            <dd style={{ margin: 0 }}>{field.value}</dd>
          </React.Fragment>
        ))}
      </dl>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button type="button" onClick={() => onApprove?.(proposal)} disabled={disabled}>
          Approve
        </button>
        <button type="button" onClick={() => onReject?.(proposal)} disabled={disabled}>
          Reject
        </button>
      </div>
    </section>
  );
}

export default AgentProposalCard;
