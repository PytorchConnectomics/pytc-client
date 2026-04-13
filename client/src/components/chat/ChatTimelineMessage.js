import React from "react";
import AgentProposalCard from "./AgentProposalCard";

function ChatTimelineMessage({ item, onApprove, onReject }) {
  if (item?.kind === "agent_proposal") {
    return (
      <AgentProposalCard
        proposal={item.proposal}
        onApprove={onApprove}
        onReject={onReject}
      />
    );
  }

  return <div>{item?.text}</div>;
}

export default ChatTimelineMessage;
