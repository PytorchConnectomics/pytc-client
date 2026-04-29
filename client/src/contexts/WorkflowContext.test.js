import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppContext } from "./GlobalContext";
import { WorkflowProvider, useWorkflow } from "./WorkflowContext";
import {
  approveAgentAction,
  appendWorkflowEvent,
  computeWorkflowEvaluationResult,
  createAgentAction,
  exportWorkflowBundle,
  getConfigPresetContent,
  getCurrentWorkflow,
  getWorkflowAgentRecommendation,
  getWorkflowHotspots,
  getWorkflowImpactPreview,
  getWorkflowPreflight,
  listWorkflowArtifacts,
  listWorkflowCorrectionSets,
  listWorkflowEvents,
  listWorkflowEvaluationResults,
  listWorkflowModelRuns,
  listWorkflowModelVersions,
} from "../api";

jest.mock("../api", () => ({
  approveAgentAction: jest.fn(),
  appendWorkflowEvent: jest.fn(),
  computeWorkflowEvaluationResult: jest.fn(),
  createAgentAction: jest.fn(),
  exportWorkflowBundle: jest.fn(),
  getConfigPresetContent: jest.fn(),
  getCurrentWorkflow: jest.fn(),
  getWorkflowAgentRecommendation: jest.fn(),
  getWorkflowHotspots: jest.fn(),
  getWorkflowImpactPreview: jest.fn(),
  getWorkflowPreflight: jest.fn(),
  listWorkflowArtifacts: jest.fn(),
  listWorkflowCorrectionSets: jest.fn(),
  listWorkflowEvents: jest.fn(),
  listWorkflowEvaluationResults: jest.fn(),
  listWorkflowModelRuns: jest.fn(),
  listWorkflowModelVersions: jest.fn(),
  queryWorkflowAgent: jest.fn(),
  rejectAgentAction: jest.fn(),
  startNewWorkflow: jest.fn(),
  updateWorkflow: jest.fn(),
}));

jest.mock("../logging/appEventLog", () => ({
  logClientEvent: jest.fn(),
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
      <div>
        {workflowContext.events.map((event) => event.event_type).join(",")}
      </div>
      <div>{workflowContext.hotspots?.[0]?.summary || "no-hotspot"}</div>
      <div>{workflowContext.impactPreview?.confidence || "no-impact"}</div>
      <div>{workflowContext.agentRecommendation?.decision || "no-agent"}</div>
      <div>{workflowContext.preflight?.overall_status || "no-preflight"}</div>
      <div>{`artifacts:${workflowContext.artifacts.length}`}</div>
      <div>{`runs:${workflowContext.modelRuns.length}`}</div>
      <div>{`corrections:${workflowContext.correctionSets.length}`}</div>
      <div>{`evaluations:${workflowContext.evaluationResults.length}`}</div>
      <button
        type="button"
        onClick={() => workflowContext.approveAgentAction(7)}
      >
        Approve proposal
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.runClientEffects({
            navigate_to: "inference",
            set_inference_output_path: "/tmp/inference-out",
          })
        }
      >
        Run effects
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.runClientEffects({
            navigate_to: "visualization",
            set_visualization_image_path: "/tmp/view-image.h5",
            set_visualization_label_path: "/tmp/view-label.h5",
            set_visualization_scales: [1, 1, 1],
          })
        }
      >
        View data effects
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.executeAssistantItem({
            id: "start-inference",
            title: "Start inference in app",
            command: "app inference run",
            client_effects: {
              navigate_to: "inference",
              set_inference_output_path: "/tmp/runtime-out",
              runtime_action: { kind: "start_inference" },
            },
          })
        }
      >
        Execute assistant item
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.runClientEffects({
            navigate_to: "mask-proofreading",
            set_proofreading_dataset_path: "/tmp/image.tif",
            set_proofreading_mask_path: "/tmp/mask.tif",
            set_proofreading_project_name: "Proofread me",
            runtime_action: { kind: "start_proofreading" },
          })
        }
      >
        Start proofreading
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.runClientEffects({
            workflow_action: {
              kind: "propose_retraining_stage",
              corrected_mask_path: "/tmp/corrected.tif",
            },
            refresh_insights: true,
          })
        }
      >
        Propose retraining
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.runClientEffects({
            navigate_to: "training",
            set_training_config_preset:
              "configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
            set_training_image_path: "/tmp/image.h5",
            set_training_label_path: "/tmp/corrected.tif",
            set_training_output_path: "/tmp/output",
            set_training_log_path: "/tmp/output",
            runtime_action: {
              kind: "start_training",
              autopick_parameters: true,
            },
          })
        }
      >
        Auto train
      </button>
      <button
        type="button"
        onClick={() =>
          workflowContext.appendEvent({
            actor: "system",
            event_type: "test.event",
            summary: "Append test event.",
          })
        }
      >
        Append event
      </button>
      <div>
        {workflowContext.pendingRuntimeAction?.kind || "no-runtime-action"}
      </div>
      <div>
        {workflowContext.pendingRuntimeAction?.overrides?.datasetPath ||
          "no-dataset-override"}
      </div>
      <div>
        {workflowContext.pendingRuntimeAction?.overrides?.inputImagePath ||
          "no-training-image-override"}
      </div>
      <div>
        {workflowContext.pendingRuntimeAction?.overrides?.autoParameters
          ? "auto-parameters"
          : "manual-parameters"}
      </div>
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
      hotspots: [
        { region_key: "z:9", summary: "Top hotspot", severity: "high" },
      ],
    });
    getWorkflowImpactPreview.mockResolvedValue({
      workflow_id: 1,
      confidence: "medium",
      summary: "Impact summary",
    });
    getWorkflowAgentRecommendation.mockResolvedValue({
      workflow_id: 1,
      stage: "setup",
      decision: "Proofread this data if the mask is ready.",
      rationale:
        "A human review pass is the fastest way to create useful edits.",
      confidence: "medium",
      next_stage: "proofreading",
      readiness: [],
      actions: [],
      commands: [],
    });
    getWorkflowPreflight.mockResolvedValue({
      workflow_id: 1,
      overall_status: "image_only",
      summary: "Image volume is loaded; add a checkpoint or mask/label next.",
      items: [],
    });
    createAgentAction.mockResolvedValue({
      id: 8,
      event_type: "agent.proposal_created",
    });
    computeWorkflowEvaluationResult.mockResolvedValue({
      id: 9,
      summary: "Before/after evaluation computed.",
    });
    exportWorkflowBundle.mockResolvedValue({
      artifacts: [{ id: 1 }],
      artifact_paths: [],
    });
    getConfigPresetContent.mockResolvedValue({
      path: "configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
      content: "DATASET: {}\nSOLVER: {}\n",
    });
    listWorkflowArtifacts.mockResolvedValue([
      { id: 1, artifact_type: "image_volume" },
    ]);
    listWorkflowModelRuns.mockResolvedValue([{ id: 2, run_type: "inference" }]);
    listWorkflowModelVersions.mockResolvedValue([]);
    listWorkflowCorrectionSets.mockResolvedValue([
      { id: 3, corrected_mask_path: "/tmp/corrected.tif" },
    ]);
    listWorkflowEvaluationResults.mockResolvedValue([
      { id: 4, metrics: { summary: { dice_delta: 0.1 } } },
    ]);
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
      expect(
        screen.getByText("Proofread this data if the mask is ready."),
      ).toBeTruthy();
      expect(screen.getByText("image_only")).toBeTruthy();
    });
    await waitFor(() => {
      expect(screen.getByText("artifacts:1")).toBeTruthy();
      expect(screen.getByText("runs:1")).toBeTruthy();
      expect(screen.getByText("corrections:1")).toBeTruthy();
      expect(screen.getByText("evaluations:1")).toBeTruthy();
    });
    expect(listWorkflowArtifacts).toHaveBeenCalledWith(1);
    expect(listWorkflowEvaluationResults).toHaveBeenCalledWith(1);
    expect(getCurrentWorkflow).toHaveBeenCalledTimes(1);
    expect(getWorkflowAgentRecommendation).toHaveBeenCalledWith(1);
    expect(getWorkflowPreflight).toHaveBeenCalledWith(1);
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

  it("exposes direct client-effect execution for chat action cards", async () => {
    const setOutputPath = jest.fn();

    renderProvider({
      trainingState: { setInputLabel: jest.fn() },
      inferenceState: { setOutputPath },
    });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("Run effects"));

    await waitFor(() => {
      expect(setOutputPath).toHaveBeenCalledWith("/tmp/inference-out");
    });
  });

  it("applies agent-selected visualization paths", async () => {
    const setCurrentImage = jest.fn();
    const setCurrentLabel = jest.fn();
    const setVisualizationScales = jest.fn();

    renderProvider({
      setCurrentImage,
      setCurrentLabel,
      setVisualizationScales,
      trainingState: { setInputLabel: jest.fn() },
    });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("View data effects"));

    await waitFor(() => {
      expect(setCurrentImage).toHaveBeenCalledWith("/tmp/view-image.h5");
      expect(setCurrentLabel).toHaveBeenCalledWith("/tmp/view-label.h5");
      expect(setVisualizationScales).toHaveBeenCalledWith("1,1,1");
    });
  });

  it("queues runtime actions and logs assistant command execution", async () => {
    const setOutputPath = jest.fn();

    renderProvider({
      trainingState: { setInputLabel: jest.fn(), setLogPath: jest.fn() },
      inferenceState: { setOutputPath, setCheckpointPath: jest.fn() },
    });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("Execute assistant item"));

    await waitFor(() => {
      expect(setOutputPath).toHaveBeenCalledWith("/tmp/runtime-out");
    });
    await waitFor(() => {
      expect(screen.getByText("start_inference")).toBeTruthy();
    });
    expect(appendWorkflowEvent).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        actor: "user",
        event_type: "assistant.command.invoked",
      }),
    );
  });

  it("loads agent-selected training config before queueing training", async () => {
    const setInputImage = jest.fn();
    const setInputLabel = jest.fn();
    const setOutputPath = jest.fn();
    const setLogPath = jest.fn();
    const setConfigOriginPath = jest.fn();
    const setSelectedYamlPreset = jest.fn();
    const setUploadedYamlFile = jest.fn();
    const setTrainingConfig = jest.fn();

    renderProvider({
      setTrainingConfig,
      trainingState: {
        setInputImage,
        setInputLabel,
        setOutputPath,
        setLogPath,
        setConfigOriginPath,
        setSelectedYamlPreset,
        setUploadedYamlFile,
      },
      inferenceState: {
        setOutputPath: jest.fn(),
        setCheckpointPath: jest.fn(),
      },
    });
    await screen.findByText("setup");
    fireEvent.click(screen.getByText("Auto train"));

    await waitFor(() => {
      expect(getConfigPresetContent).toHaveBeenCalledWith(
        "configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
      );
      expect(setTrainingConfig).toHaveBeenCalledWith(
        "DATASET: {}\nSOLVER: {}\n",
      );
      expect(setInputImage).toHaveBeenCalledWith("/tmp/image.h5");
      expect(setInputLabel).toHaveBeenCalledWith("/tmp/corrected.tif");
      expect(setOutputPath).toHaveBeenCalledWith("/tmp/output");
      expect(screen.getByText("start_training")).toBeTruthy();
      expect(screen.getByText("/tmp/image.h5")).toBeTruthy();
      expect(screen.getByText("auto-parameters")).toBeTruthy();
    });
  });

  it("queues proofreading runtime actions with image and mask overrides", async () => {
    renderProvider({
      trainingState: { setInputLabel: jest.fn(), setLogPath: jest.fn() },
      inferenceState: {
        setOutputPath: jest.fn(),
        setCheckpointPath: jest.fn(),
      },
    });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("Start proofreading"));

    await waitFor(() => {
      expect(screen.getByText("start_proofreading")).toBeTruthy();
      expect(screen.getByText("/tmp/image.tif")).toBeTruthy();
    });
  });

  it("creates approval-gated retraining proposals from client workflow actions", async () => {
    renderProvider({
      trainingState: { setInputLabel: jest.fn() },
      inferenceState: { setOutputPath: jest.fn() },
    });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("Propose retraining"));

    await waitFor(() => {
      expect(createAgentAction).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          action: "stage_retraining_from_corrections",
          payload: { corrected_mask_path: "/tmp/corrected.tif" },
        }),
      );
    });
    expect(getWorkflowHotspots).toHaveBeenCalledWith(1);
  });

  it("does not throw when noncritical workflow event append fails", async () => {
    appendWorkflowEvent.mockRejectedValueOnce(new Error("Network Error"));

    renderProvider({
      trainingState: { setInputLabel: jest.fn() },
      inferenceState: { setOutputPath: jest.fn() },
    });
    await screen.findByText("setup");

    fireEvent.click(screen.getByText("Append event"));

    await waitFor(() => {
      expect(appendWorkflowEvent).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ event_type: "test.event" }),
      );
    });
    expect(screen.getByText("workflow.created")).toBeTruthy();
  });
});
