import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import AgentProposalCard from "../components/chat/AgentProposalCard";

jest.mock("antd", () => ({
  Button: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
  Space: ({ children }) => <div>{children}</div>,
  Tag: ({ children }) => <span>{children}</span>,
  Typography: {
    Text: ({ children }) => <span>{children}</span>,
  },
}));

describe("AgentProposalCard", () => {
  it("renders hotspot proposal fields and approve/reject actions", () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    const proposal = {
      type: "prioritize_failure_hotspots",
      rationale: "Focus annotation where the model fails most often.",
      target_dataset: "set-a",
      hotspots: ["z:11", "z:12"],
      priority_metric: "error_rate",
      min_failure_rate: 0.2,
    };

    render(
      <AgentProposalCard
        proposal={proposal}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByText("Prioritize Failure Hotspots")).toBeTruthy();
    expect(screen.getByText("set-a")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(onApprove).toHaveBeenCalledWith(proposal);
    expect(onReject).toHaveBeenCalledWith(proposal);
  });

  it("supports correction-impact cards with compact rationale", () => {
    const proposal = {
      proposal_type: "preview_correction_impact",
      rationale: "A".repeat(200),
      target_metric: "f1",
      expected_delta: "+0.05",
      sample_size: 128,
      confidence: "high",
    };

    render(<AgentProposalCard proposal={proposal} />);

    expect(screen.getByText("Preview Correction Impact")).toBeTruthy();
    expect(screen.getByText(/A{157}…/)).toBeTruthy();
    expect(screen.getByText("+0.05")).toBeTruthy();
  });

  it("renders fallback proposal content", () => {
    render(
      <AgentProposalCard
        proposal={{ type: "custom_type", rationale: "Keep behavior stable", foo: "bar" }}
      />,
    );

    expect(screen.getByText("Agent Proposal")).toBeTruthy();
    expect(screen.getByText("Keep behavior stable")).toBeTruthy();
    expect(screen.getByText("bar")).toBeTruthy();
  });
});
