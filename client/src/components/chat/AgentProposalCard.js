import React from "react";
import { buildProposalSummary, getProposalCardConfig } from "../../contexts/workflow/proposalCardConfig";

const CARD_STYLE = {
  border: "1px solid #d9d9d9",
  borderRadius: 8,
  padding: 12,
  marginTop: 8,
  background: "#fff",
};

function truncate(text, maxLength = 180) {
  if (!text) return "";
  return text.length <= maxLength ? text : `${text.slice(0, maxLength).trimEnd()}…`;
}

function ProposalSummary({ summary }) {
  if (!summary.length) return null;

  return (
    <ul style={{ paddingLeft: 20, margin: "8px 0" }}>
      {summary.map(({ label, value }) => (
        <li key={label}>
          <strong>{label}:</strong> {value}
        </li>
      ))}
    </ul>
  );
}

export default function AgentProposalCard({ proposal, onApprove, onReject }) {
  const config = getProposalCardConfig(proposal?.type);

  if (!config) return null;

  const summary = buildProposalSummary(proposal);

  return (
    <article style={CARD_STYLE} data-testid={`proposal-card-${proposal.type}`}>
      <h4 style={{ margin: "0 0 4px" }}>{config.title}</h4>
      <p style={{ margin: "0 0 8px", color: "#666" }}>{config.description}</p>

      {proposal?.rationale ? (
        <p style={{ margin: "0 0 8px" }}>
          <strong>Rationale:</strong> {truncate(proposal.rationale)}
        </p>
      ) : null}

      <ProposalSummary summary={summary} />

      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button onClick={() => onApprove?.(proposal)} type="button">
          Approve
        </button>
        <button onClick={() => onReject?.(proposal)} type="button">
          Reject
        </button>
      </div>
    </article>
  );
}
