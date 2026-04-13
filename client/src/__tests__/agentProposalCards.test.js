import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import AgentProposalCard from "../components/chat/AgentProposalCard";

describe("AgentProposalCard", () => {
  it("renders prioritize_failure_hotspots with approve/reject", () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    const proposal = {
      type: "prioritize_failure_hotspots",
      rationale: "Focus annotation time where model uncertainty is highest.",
      target_dataset: "set-a",
      hotspots: ["slice_01", "slice_10"],
      priority_metric: "uncertainty",
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
    expect(
      screen.getByText(/Focus annotation time where model uncertainty is highest./),
    ).toBeTruthy();
    expect(screen.getByText("set-a")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(onApprove).toHaveBeenCalledWith(proposal);
    expect(onReject).toHaveBeenCalledWith(proposal);
  });

  it("renders preview_correction_impact with compact rationale", () => {
    const proposal = {
      proposal_type: "preview_correction_impact",
      rationale:
        "A".repeat(200),
      target_metric: "f1",
      expected_delta: "+0.05",
      sample_size: 128,
      confidence: "high",
    };

    render(<AgentProposalCard proposal={proposal} />);

    expect(screen.getByText("Preview Correction Impact")).toBeTruthy();
    expect(screen.getByText(/A{157}…/)).toBeTruthy();
    expect(screen.getByText("f1")).toBeTruthy();
    expect(screen.getByText("+0.05")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reject" })).toBeTruthy();
  });

  it("keeps fallback proposal rendering for existing types", () => {
    render(
      <AgentProposalCard
        proposal={{ type: "existing_type", rationale: "Keep behavior stable", foo: "bar" }}
      />,
    );

    expect(screen.getByText("Agent Proposal")).toBeTruthy();
    expect(screen.getByText("Keep behavior stable")).toBeTruthy();
    expect(screen.getByText("bar")).toBeTruthy();
  });
});
