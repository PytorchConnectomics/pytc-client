import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import AgentProposalCard from "../components/chat/AgentProposalCard";
import { renderAgentTimelineItem } from "../components/chat/renderAgentTimelineItem";

describe("Agent proposal cards", () => {
  it("renders prioritize_failure_hotspots cards with compact rationale and fields", () => {
    render(
      <AgentProposalCard
        proposal={{
          type: "prioritize_failure_hotspots",
          rationale:
            "Recent runs surfaced unstable boundaries around densely packed synapses, so we should route reviewers to these hotspots first.",
          focus_metric: "boundary_instability",
          max_hotspots: 12,
          dataset_split: "validation",
        }}
      />,
    );

    expect(screen.getByText("Prioritize Failure Hotspots")).toBeTruthy();
    expect(screen.getByText(/Rationale:/)).toBeTruthy();
    expect(screen.getByText(/Focus metric:/)).toBeTruthy();
    expect(screen.getByText(/Max hotspots:/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reject" })).toBeTruthy();
  });

  it("renders preview_correction_impact cards and wires action buttons", () => {
    const onApprove = jest.fn();
    const onReject = jest.fn();
    const proposal = {
      type: "preview_correction_impact",
      rationale:
        "Estimate if the correction can reduce merges before applying edits to the shared model state.",
      target_slice_id: "z-0142",
      correction_mode: "merge_split_fix",
      estimated_impact: "-18% merge errors",
    };

    render(
      <AgentProposalCard proposal={proposal} onApprove={onApprove} onReject={onReject} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(screen.getByText("Preview Correction Impact")).toBeTruthy();
    expect(onApprove).toHaveBeenCalledWith(proposal);
    expect(onReject).toHaveBeenCalledWith(proposal);
  });

  it("keeps existing non-proposal timeline rendering unaffected", () => {
    render(renderAgentTimelineItem({ kind: "assistant", content: "No proposal here." }));

    expect(screen.getByText("No proposal here.")).toBeTruthy();
  });
});
