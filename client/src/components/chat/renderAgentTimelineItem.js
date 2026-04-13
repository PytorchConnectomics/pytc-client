import React from "react";
import AgentProposalCard from "./AgentProposalCard";

export function renderAgentTimelineItem(message, handlers = {}) {
  if (message?.kind === "proposal") {
    return (
      <AgentProposalCard
        proposal={message.proposal}
        onApprove={handlers.onApproveProposal}
        onReject={handlers.onRejectProposal}
      />
    );
  }

  return <span>{message?.content ?? ""}</span>;
}
