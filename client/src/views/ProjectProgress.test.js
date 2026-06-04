import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ProjectProgress from "./ProjectProgress";

let mockWorkflowContext;

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: () => mockWorkflowContext,
}));

jest.mock("../logging/appEventLog", () => ({
  logClientEvent: jest.fn(),
}));

describe("ProjectProgress", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.matchMedia = jest.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    mockWorkflowContext = {
      workflow: { id: 1 },
      workflowOverview: {
        phase: "proofread",
        phase_label: "Proofread",
        phase_reason: "One draft mask still needs review.",
        stages: [
          {
            id: "setup",
            label: "Setup",
            target_view: "files",
            complete: true,
            current: false,
          },
          {
            id: "proofread",
            label: "Proofread",
            target_view: "mask-proofreading",
            complete: false,
            current: true,
          },
        ],
        blockers: [
          {
            id: "draft_masks_need_review",
            label: "Draft masks need review",
            detail: "1 volume has a mask that is not marked ground truth.",
            target_view: "mask-proofreading",
          },
        ],
        recommended_next_actions: [
          {
            id: "proofread-draft-masks",
            label: "Proofread draft masks",
            detail: "Review the draft mask before treating it as ground truth.",
            target_view: "mask-proofreading",
            client_effects: { navigate_to: "mask-proofreading" },
          },
        ],
        active_runs: [],
      },
      projectProgress: {
        summary: {
          total: 3,
          tracked_total: 3,
          ground_truth: 1,
          needs_proofreading: 1,
          missing_segmentation: 1,
          remaining: 2,
          completion_pct: 33.3,
          segmentation_coverage_pct: 66.7,
        },
        status_definitions: {},
        volumes: [
          {
            id: "data/image/vol_a_im.h5",
            name: "vol_a_im.h5",
            status: "ground_truth",
            status_label: "Fully good",
            status_source: "path_marker",
            image_path: "/tmp/project/data/image/vol_a_im.h5",
            segmentation_path: "/tmp/project/data/seg/vol_a_gt.h5",
            segmentation_kind: "label",
            volume_set_name: "image + seg",
          },
        ],
      },
      refreshProjectProgress: jest.fn().mockResolvedValue({
        summary: { total: 3 },
      }),
      updateProjectProgressVolume: jest.fn().mockResolvedValue({}),
      runClientEffects: jest.fn().mockResolvedValue(),
    };
  });

  it("renders the workflow project progress summary", async () => {
    render(<ProjectProgress />);

    expect(await screen.findByText("Workflow Overview")).toBeTruthy();
    expect(screen.getByText("Current phase: Proofread")).toBeTruthy();
    expect(screen.getByText("Recommended next moves")).toBeTruthy();
    expect(screen.getByText("Tracked volumes")).toBeTruthy();
    expect(screen.getAllByText("Fully good").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Needs proofreading").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No segmentation").length).toBeGreaterThan(0);
    expect(screen.getByText("vol_a_im.h5")).toBeTruthy();
    await waitFor(() => {
      expect(mockWorkflowContext.refreshProjectProgress).toHaveBeenCalled();
    });
  });

  it("refreshes on demand", async () => {
    render(<ProjectProgress />);

    await waitFor(() => {
      expect(mockWorkflowContext.refreshProjectProgress).toHaveBeenCalledTimes(1);
    });
    const refreshButton = screen.getByRole("button", { name: /Refresh/ });
    await waitFor(() => {
      expect(refreshButton.className).not.toContain("ant-btn-loading");
    });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockWorkflowContext.refreshProjectProgress).toHaveBeenCalledTimes(2);
    });
  });
});
