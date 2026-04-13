import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AgentProposalCard from "../components/chat/AgentProposalCard";

describe("AgentProposalCard", () => {
  test("renders prioritize_failure_hotspots card and actions", async () => {
    const user = userEvent.setup();
    const onApprove = jest.fn();
    const onReject = jest.fn();
    const proposal = {
      type: "prioritize_failure_hotspots",
      rationale: "Focus review on areas with recurrent model misses.",
      payload: {
        priority_metric: "error_density",
        max_hotspots: 5,
        candidate_count: 12,
      },
    };

    render(
      <AgentProposalCard
        proposal={proposal}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByText("Prioritize Failure Hotspots")).toBeInTheDocument();
    expect(screen.getByText(/recurrent model misses/i)).toBeInTheDocument();
    expect(screen.getByText(/Priority metric:/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(onApprove).toHaveBeenCalledWith(proposal);
    expect(onReject).toHaveBeenCalledWith(proposal);
  });

  test("renders preview_correction_impact card and actions", async () => {
    const user = userEvent.setup();
    const onApprove = jest.fn();
    const onReject = jest.fn();
    const proposal = {
      type: "preview_correction_impact",
      rationale: "Estimate impact before applying batch corrections.",
      payload: {
        target_region: "slice_020-030",
        estimated_quality_gain: "+4.2% IoU",
        confidence: "high",
      },
    };

    render(
      <AgentProposalCard
        proposal={proposal}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByText("Preview Correction Impact")).toBeInTheDocument();
    expect(screen.getByText(/Estimate impact/i)).toBeInTheDocument();
    expect(screen.getByText(/Target region:/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(onApprove).toHaveBeenCalledWith(proposal);
    expect(onReject).toHaveBeenCalledWith(proposal);
  });

  test("falls back for unknown proposal types", () => {
    const renderFallback = jest.fn(() => <div>Existing card renderer</div>);

    render(
      <AgentProposalCard
        proposal={{ type: "legacy_proposal", payload: {} }}
        renderFallback={renderFallback}
      />,
    );

    expect(renderFallback).toHaveBeenCalled();
    expect(screen.getByText("Existing card renderer")).toBeInTheDocument();
  });
});
