import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import WorkflowEvidencePanel from "./WorkflowEvidencePanel";
import { WorkflowContext } from "../../contexts/WorkflowContext";
import { computeWorkflowEvaluationResult, exportWorkflowBundle } from "../../api";

jest.mock("../../api", () => ({
  computeWorkflowEvaluationResult: jest.fn(),
  exportWorkflowBundle: jest.fn(),
}));

jest.mock("antd", () => {
  const React = require("react");
  const Card = ({ title, extra, children }) => (
    <section>
      <header>
        {title}
        {extra}
      </header>
      {children}
    </section>
  );
  const Empty = ({ description }) => <div>{description}</div>;
  Empty.PRESENTED_IMAGE_SIMPLE = "simple";
  return {
    Button: ({ children, loading, ...props }) => (
      <button type="button" {...props}>
        {children}
      </button>
    ),
    Card,
    Empty,
    Input: ({ ...props }) => <input {...props} />,
    Space: ({ children }) => <div>{children}</div>,
    Tag: ({ children }) => <span>{children}</span>,
    Typography: {
      Text: ({ children }) => <span>{children}</span>,
    },
  };
});

jest.mock("../../contexts/WorkflowContext", () => {
  const React = require("react");
  const WorkflowContext = React.createContext(null);
  return {
    WorkflowContext,
    useWorkflow: () => React.useContext(WorkflowContext),
  };
});

function renderPanel(value = {}) {
  const contextValue = {
    workflow: {
      id: 11,
      stage: "evaluation",
      image_path: "/tmp/image.tif",
      corrected_mask_path: "/tmp/corrected-mask.tif",
    },
    events: [
      {
        id: 9,
        event_type: "workflow.bundle_exported",
      },
    ],
    artifacts: [
      {
        id: 1,
        artifact_type: "inference_output",
        role: "prediction",
        path: "/tmp/baseline-prediction.tif",
        exists: true,
      },
      {
        id: 2,
        artifact_type: "inference_output",
        role: "prediction",
        path: "/tmp/candidate-prediction.tif",
        exists: true,
      },
      {
        id: 3,
        artifact_type: "correction_set",
        role: "corrected_mask",
        path: "/tmp/corrected-mask.tif",
        exists: true,
      },
    ],
    modelRuns: [
      {
        id: 4,
        run_type: "inference",
        status: "completed",
        output_path: "/tmp/baseline-prediction.tif",
        created_at: "2026-04-25T10:00:00Z",
      },
      {
        id: 5,
        run_type: "inference",
        status: "completed",
        output_path: "/tmp/candidate-prediction.tif",
        created_at: "2026-04-25T10:10:00Z",
      },
    ],
    modelVersions: [
      {
        id: 8,
        version_label: "candidate",
        status: "candidate",
      },
    ],
    correctionSets: [
      {
        id: 6,
        corrected_mask_path: "/tmp/corrected-mask.tif",
        edit_count: 12,
        region_count: 3,
        created_at: "2026-04-25T10:05:00Z",
      },
    ],
    evaluationResults: [
      {
        id: 7,
        name: "before-after",
        summary: "Before/after evaluation computed.",
        report_path: "/tmp/evaluation-report.json",
        created_at: "2026-04-25T10:15:00Z",
        metadata: {
          baseline_prediction_path: "/tmp/baseline-prediction.tif",
          candidate_prediction_path: "/tmp/candidate-prediction.tif",
          ground_truth_path: "/tmp/ground-truth.tif",
        },
        metrics: {
          baseline: { dice: 0.5, iou: 0.4, voxel_accuracy: 0.8 },
          candidate: { dice: 0.75, iou: 0.6, voxel_accuracy: 0.9 },
          delta: { dice: 0.25, iou: 0.2, voxel_accuracy: 0.1 },
          summary: {
            dice_delta: 0.25,
            iou_delta: 0.2,
            voxel_accuracy_delta: 0.1,
            candidate_improved_dice: true,
          },
        },
      },
    ],
    refreshEvidence: jest.fn(),
    refreshEvents: jest.fn(),
    ...value,
  };

  render(
    <WorkflowContext.Provider value={contextValue}>
      <WorkflowEvidencePanel />
    </WorkflowContext.Provider>,
  );
  return contextValue;
}

describe("WorkflowEvidencePanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    computeWorkflowEvaluationResult.mockResolvedValue({
      summary: "Before/after evaluation computed. Dice delta: 0.25.",
    });
    exportWorkflowBundle.mockResolvedValue({
      artifacts: [{ id: 1 }, { id: 2 }],
      model_runs: [{ id: 3 }],
      evaluation_results: [{ id: 4 }],
      artifact_paths: [
        { path: "/tmp/a.tif", exists: true },
        { path: "/tmp/missing.tif", exists: false },
      ],
    });
  });

  it("renders baseline, candidate, corrected mask, and metric deltas", () => {
    renderPanel();

    expect(screen.getByText("Review status")).toBeTruthy();
    expect(screen.getByText("new result improved")).toBeTruthy();
    expect(screen.getByText("Previous result")).toBeTruthy();
    expect(screen.getByText("/tmp/baseline-prediction.tif")).toBeTruthy();
    expect(screen.getByText("New result")).toBeTruthy();
    expect(screen.getByText("/tmp/candidate-prediction.tif")).toBeTruthy();
    expect(screen.getByText("Your saved edits")).toBeTruthy();
    expect(screen.getByText("/tmp/corrected-mask.tif")).toBeTruthy();
    expect(screen.getByText("Dice +0.25")).toBeTruthy();
    expect(screen.getByText("IoU +0.2")).toBeTruthy();
    expect(screen.getByText("Accuracy +0.1")).toBeTruthy();
    expect(screen.getByText("Before/after evaluation computed.")).toBeTruthy();
    expect(screen.getByText("Report: /tmp/evaluation-report.json")).toBeTruthy();
    expect(screen.getByText("Loop progress")).toBeTruthy();
    expect(screen.getByText("ready")).toBeTruthy();
  });

  it("exposes a refresh action for current workflow evidence", () => {
    const value = renderPanel();

    fireEvent.click(screen.getByText("Refresh"));

    expect(value.refreshEvidence).toHaveBeenCalledTimes(1);
  });

  it("computes before/after metrics from recorded evidence paths", async () => {
    const value = renderPanel();

    fireEvent.click(screen.getByText("Compare results"));

    await waitFor(() => {
      expect(computeWorkflowEvaluationResult).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          name: "workflow-before-after-evaluation",
          baseline_prediction_path: "/tmp/baseline-prediction.tif",
          candidate_prediction_path: "/tmp/candidate-prediction.tif",
          ground_truth_path: "/tmp/ground-truth.tif",
          baseline_run_id: 4,
          candidate_run_id: 5,
          metadata: expect.objectContaining({
            source: "workflow_evidence_panel",
            corrected_mask_path: "/tmp/corrected-mask.tif",
          }),
        }),
      );
    });
    await waitFor(() => {
      expect(value.refreshEvidence).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText("Before/after evaluation computed. Dice delta: 0.25."),
      ).toBeTruthy();
    });
  });

  it("passes dataset, crop, and channel controls into metric computation", async () => {
    renderPanel();

    fireEvent.click(screen.getByText("Metric options"));
    fireEvent.change(screen.getByLabelText("Baseline dataset key"), {
      target: { value: "vol0" },
    });
    fireEvent.change(screen.getByLabelText("Candidate dataset key"), {
      target: { value: "vol0" },
    });
    fireEvent.change(screen.getByLabelText("Ground truth dataset key"), {
      target: { value: "data" },
    });
    fireEvent.change(screen.getByLabelText("Evaluation crop"), {
      target: { value: "0:4,0:128,0:128" },
    });
    fireEvent.change(screen.getByLabelText("Baseline channel"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Candidate channel"), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByText("Compare results"));

    await waitFor(() => {
      expect(computeWorkflowEvaluationResult).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          baseline_dataset: "vol0",
          candidate_dataset: "vol0",
          ground_truth_dataset: "data",
          crop: "0:4,0:128,0:128",
          baseline_channel: 1,
          candidate_channel: 1,
        }),
      );
    });
  });

  it("exports a workflow bundle and summarizes artifact existence", async () => {
    const value = renderPanel();

    fireEvent.click(screen.getByText("Export report"));

    await waitFor(() => {
      expect(exportWorkflowBundle).toHaveBeenCalledWith(11);
      expect(
        screen.getByText(
          "Report exported: 2 files, 1 runs, 1 comparisons, 1 missing paths.",
        ),
      ).toBeTruthy();
    });
    expect(value.refreshEvents).toHaveBeenCalledTimes(1);
  });

  it("blocks metric computation until all required paths are recorded", () => {
    renderPanel({
      evaluationResults: [],
      modelRuns: [],
      artifacts: [],
      workflow: { id: 11, stage: "evaluation" },
    });

    expect(screen.getByText("Compare results").disabled).toBe(true);
    expect(
      screen.getByText(
        /Need previous result, new result, reference mask/,
      ),
    ).toBeTruthy();
  });

  it("shows an empty state without an active workflow", () => {
    render(
      <WorkflowContext.Provider value={{ workflow: null }}>
        <WorkflowEvidencePanel />
      </WorkflowContext.Provider>,
    );

    expect(screen.getByText("No active workflow yet")).toBeTruthy();
  });
});
