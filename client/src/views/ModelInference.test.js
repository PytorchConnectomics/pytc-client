import React from "react";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";

import ModelInference from "./ModelInference";
import { AppContext } from "../contexts/GlobalContext";
import {
  getInferenceLogs,
  getInferenceStatus,
  syncWorkflowInferenceRuntime,
} from "../api";

const mockAppendWorkflowEvent = jest.fn();
const mockRefreshWorkflow = jest.fn();
const mockRefreshEvents = jest.fn();
const mockRefreshInsights = jest.fn();
const mockRefreshEvidence = jest.fn();

jest.mock("../api", () => ({
  getInferenceLogs: jest.fn(),
  getInferenceStatus: jest.fn(),
  syncWorkflowInferenceRuntime: jest.fn(),
  stopModelInference: jest.fn(),
}));

jest.mock("../runtime/modelLaunch", () => ({
  getPathValue: (value) => value,
  launchInferenceFromContext: jest.fn(),
}));

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: () => ({
    workflow: { id: 42, stage: "inference" },
    appendEvent: mockAppendWorkflowEvent,
    refreshWorkflow: mockRefreshWorkflow,
    refreshEvents: mockRefreshEvents,
    refreshInsights: mockRefreshInsights,
    refreshEvidence: mockRefreshEvidence,
    pendingRuntimeAction: null,
    consumeRuntimeAction: jest.fn(),
  }),
}));

jest.mock("../components/Configurator", () => () => <div>Configurator</div>);
jest.mock("../components/RuntimeLogPanel", () => () => <div>Runtime Log</div>);
jest.mock("../components/workflow/StageHeader", () => ({ title }) => (
  <h1>{title}</h1>
));

function renderInference(props = {}) {
  const setIsInferring = props.setIsInferring || jest.fn();
  render(
    <AppContext.Provider
      value={{
        inferenceState: {
          outputPath: "/tmp/inference-out",
          checkpointPath: "/tmp/checkpoint.pth.tar",
        },
      }}
    >
      <ModelInference
        isInferring={props.isInferring ?? true}
        setIsInferring={setIsInferring}
      />
    </AppContext.Provider>,
  );
  return { setIsInferring };
}

describe("ModelInference", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    getInferenceLogs.mockResolvedValue({ phase: "finished", metadata: {} });
    getInferenceStatus.mockResolvedValue({
      isRunning: false,
      exitCode: 0,
      phase: "finished",
      lastError: null,
    });
    syncWorkflowInferenceRuntime.mockResolvedValue({
      synced: true,
      outputPath: "/tmp/inference-out/result_xy.h5",
    });
  });

  afterEach(() => {
    cleanup();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("syncs completed inference runtime instead of appending a duplicate event", async () => {
    const { setIsInferring } = renderInference();

    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    await waitFor(() => {
      expect(syncWorkflowInferenceRuntime).toHaveBeenCalledWith(42);
    });
    expect(setIsInferring).toHaveBeenCalledWith(false);
    expect(mockRefreshWorkflow).toHaveBeenCalled();
    expect(mockRefreshEvents).toHaveBeenCalled();
    expect(mockRefreshInsights).toHaveBeenCalled();
    expect(mockRefreshEvidence).toHaveBeenCalled();
    expect(mockAppendWorkflowEvent).not.toHaveBeenCalled();
    expect(
      await screen.findByText(
        /Inference completed and workflow synced: \/tmp\/inference-out\/result_xy.h5/,
      ),
    ).toBeTruthy();
  });

  it("falls back to workflow event append when runtime sync does not capture an artifact", async () => {
    syncWorkflowInferenceRuntime.mockResolvedValueOnce({
      synced: false,
      reason: "prediction_artifact_not_found",
    });

    renderInference();

    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    await waitFor(() => {
      expect(mockAppendWorkflowEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "inference.completed",
          payload: expect.objectContaining({
            syncReason: "prediction_artifact_not_found",
          }),
        }),
      );
    });
  });
});
