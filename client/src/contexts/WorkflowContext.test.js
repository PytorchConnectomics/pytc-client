import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppContext } from "./GlobalContext";
import { WorkflowProvider, useWorkflow } from "./WorkflowContext";
import {
  approveAgentAction,
  getCurrentWorkflow,
  getWorkflowHotspots,
  getWorkflowImpactPreview,
  listWorkflowEvents,
} from "../api";

jest.mock("../api", () => ({
  approveAgentAction: jest.fn(),
  appendWorkflowEvent: jest.fn(),
  createAgentAction: jest.fn(),
  getCurrentWorkflow: jest.fn(),
  getWorkflowHotspots: jest.fn(),
  getWorkflowImpactPreview: jest.fn(),
  listWorkflowEvents: jest.fn(),
  queryWorkflowAgent: jest.fn(),
  rejectAgentAction: jest.fn(),
  updateWorkflow: jest.fn(),
}));

const baseWorkflow = {
  id: 1,
  title: "Segmentation Workflow",
  stage: "setup",
};

function Probe() {
  const workflowContext = useWorkflow();
  return (
    <div>
      <div>{workflowContext.workflow?.stage || "loading"}</div>
      <div>{workflowContext.events.map((event) => event.event_type).join(",")}</div>
      <div>{workflowContext.hotspots?.[0]?.summary || "no-hotspot"}</div>
      <div>{workflowContext.impactPreview?.confidence || "no-impact"}</div>
      <button
        type="button"
        onClick={() => workflowContext.approveAgentAction(7)}
      >
        Approve proposal
      </button>
    </div>
  );
}

function renderProvider(appContextValue) {
  render(
    <AppContext.Provider value={appContextValue}>
      <WorkflowProvider>
        <Probe />
      </WorkflowProvider>
    </AppContext.Provider>,
  );
}

describe("WorkflowProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getCurrentWorkflow.mockResolvedValue({
      workflow: baseWorkflow,
      events: [{ id: 1, event_type: "workflow.created" }],
    });
    listWorkflowEvents.mockResolvedValue([]);
    getWorkflowHotspots.mockResolvedValue({
      workflow_id: 1,
      hotspots: [{ region_key: "z:9", summary: "Top hotspot", severity: "high" }],
    });
    getWorkflowImpactPreview.mockResolvedValue({
      workflow_id: 1,
      confidence: "medium",
      summary: "Impact summary",
    });
  });

  it("loads the current workflow and events on startup", async () => {
    renderProvider({ trainingState: { setInputLabel: jest.fn() } });

    expect(await screen.findByText("setup")).toBeTruthy();
    expect(screen.getByText("workflow.created")).toBeTruthy();
    await waitFor(() => {
      expect(getWorkflowHotspots).toHaveBeenCalledWith(1);
      expect(getWorkflowImpactPreview).toHaveBeenCalledWith(1);
    });
    await waitFor(() => {
      expect(screen.getByText("Top hotspot")).toBeTruthy();
      expect(screen.getByText("medium")).toBeTruthy();
    });
    expect(getCurrentWorkflow).toHaveBeenCalledTimes(1);
  });

  it("applies client effects when an agent proposal is approved", async () => {
    const setInputLabel = jest.fn();
    approveAgentAction.mockResolvedValue({
      workflow: { ...baseWorkflow, stage: "retraining_staged" },
      client_effects: {
        navigate_to: "training",
        set_training_label_path: "/tmp/corrected.tif",
      },
    });

    renderProvider({ trainingState: { setInputLabel } });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("Approve proposal"));

    await waitFor(() => {
      expect(setInputLabel).toHaveBeenCalledWith("/tmp/corrected.tif");
    });
    await waitFor(() => {
      expect(screen.getByText("retraining_staged")).toBeTruthy();
    });
  });
});
