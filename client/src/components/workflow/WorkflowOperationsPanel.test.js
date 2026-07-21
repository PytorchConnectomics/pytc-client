import React from "react";
import "@testing-library/jest-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  cancelWorkflowOperation,
  listWorkflowOperations,
  runWorkflowCommand,
} from "../../api";
import { useWorkflow } from "../../contexts/WorkflowContext";
import { createAppQueryClient } from "../../queryClient";
import WorkflowOperationsPanel, {
  canRetryOperation,
  getOperationsRefetchInterval,
  getWorkflowOperationsQueryOptions,
} from "./WorkflowOperationsPanel";

jest.mock("../../contexts/WorkflowContext", () => ({
  useWorkflow: jest.fn(),
}));

jest.mock("../../api", () => ({
  cancelWorkflowOperation: jest.fn(),
  listWorkflowOperations: jest.fn(),
  runWorkflowCommand: jest.fn(),
}));

const operation = (overrides = {}) => ({
  id: 1,
  workflow_id: 11,
  operation_type: "training",
  status: "queued",
  correlation_id: "corr-queued",
  input: { config_path: "/tmp/train.yaml" },
  result: {},
  error: {},
  metadata: {},
  progress: null,
  attempt_count: 0,
  cancellation_requested_at: null,
  updated_at: "2026-07-21T13:00:00Z",
  ...overrides,
});

const operations = [
  operation(),
  operation({
    id: 2,
    operation_type: "inference",
    status: "running",
    correlation_id: "corr-running",
    progress: 0.42,
    attempt_count: 1,
    cancellation_requested_at: "2026-07-21T13:01:00Z",
  }),
  operation({
    id: 3,
    operation_type: "evaluation",
    status: "succeeded",
    correlation_id: "corr-succeeded",
  }),
  operation({
    id: 4,
    operation_type: "start_training",
    status: "failed",
    correlation_id: "corr-retryable",
    command_id: 44,
    error: { status_code: 503, detail: "Worker unavailable" },
    metadata: {
      command_type: "start_training",
      execution_scope: "worker_submission",
    },
  }),
  operation({
    id: 5,
    operation_type: "export",
    status: "failed",
    correlation_id: "corr-not-retryable",
    error: { detail: "Invalid export destination" },
  }),
  operation({
    id: 6,
    operation_type: "inference",
    status: "cancelled",
    correlation_id: "corr-cancelled",
    cancellation_requested_at: "2026-07-21T13:02:00Z",
  }),
];

const renderPanel = () => {
  const queryClient = createAppQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkflowOperationsPanel />
    </QueryClientProvider>,
  );
};

describe("WorkflowOperationsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useWorkflow.mockReturnValue({ workflow: { id: 11 } });
    listWorkflowOperations.mockResolvedValue(operations);
    cancelWorkflowOperation.mockResolvedValue(
      operation({
        status: "cancelled",
        cancellation_requested_at: "2026-07-21T13:03:00Z",
      }),
    );
    runWorkflowCommand.mockResolvedValue({
      operation: operation({ id: 7, status: "succeeded" }),
    });
  });

  it("renders durable states, cancellation phases, progress, and references", async () => {
    renderPanel();

    expect(await screen.findByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Succeeded")).toBeInTheDocument();
    expect(screen.getAllByText("Failed")).toHaveLength(2);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByText("Cancellation requested")).toBeInTheDocument();
    expect(screen.getByText("Cancellation acknowledged")).toBeInTheDocument();
    expect(screen.getByText("Ref corr-running")).toBeInTheDocument();
    expect(screen.getByLabelText("Inference progress")).toBeInTheDocument();
    expect(screen.getByText("Worker unavailable")).toBeInTheDocument();
  });

  it("requests cancellation and replaces the operation with acknowledged state", async () => {
    listWorkflowOperations
      .mockResolvedValueOnce([operations[0]])
      .mockResolvedValueOnce([
        operation({
          status: "cancelled",
          cancellation_requested_at: "2026-07-21T13:03:00Z",
        }),
      ]);
    renderPanel();
    await screen.findByText("Queued");

    expect(screen.getAllByText("Cancel")).toHaveLength(1);
    fireEvent.click(screen.getByText("Cancel"));
    fireEvent.click(await screen.findByText("Cancel operation"));

    await waitFor(() => {
      expect(cancelWorkflowOperation).toHaveBeenCalledWith(
        11,
        1,
        "Cancelled from the workflow operations panel.",
      );
      expect(screen.getByText("Cancellation acknowledged")).toBeInTheDocument();
    });
  });

  it("only retries operations with explicit replay evidence", async () => {
    renderPanel();
    await screen.findByText("Queued");

    expect(screen.getAllByText("Retry")).toHaveLength(1);
    fireEvent.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(runWorkflowCommand).toHaveBeenCalledWith(11, 44);
    });
  });

  it("offers reconnect after a list request fails", async () => {
    listWorkflowOperations
      .mockRejectedValueOnce(new Error("Server unavailable"))
      .mockResolvedValueOnce([]);
    renderPanel();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Reconnect operation history",
      }),
    );

    await waitFor(() => {
      expect(listWorkflowOperations).toHaveBeenCalledTimes(2);
      expect(
        screen.getByText("No durable operations recorded"),
      ).toBeInTheDocument();
    });
  });
});

describe("workflow operation polling and retry policy", () => {
  it("polls only while at least one operation is active", () => {
    const queryOptions = getWorkflowOperationsQueryOptions(11);
    expect(queryOptions.refetchOnReconnect).toBe("always");
    expect(queryOptions.refetchInterval).toBe(getOperationsRefetchInterval);
    expect(
      queryOptions.refetchInterval({
        state: { data: [operation({ status: "running" })] },
      }),
    ).toBe(2500);
    expect(
      queryOptions.refetchInterval({
        state: { data: [operation({ status: "succeeded" })] },
      }),
    ).toBe(false);
  });

  it("requires backend replay metadata, input, and a command reference", () => {
    const retryable = operations.find((item) => item.id === 4);
    expect(canRetryOperation(retryable)).toBe(true);
    expect(canRetryOperation({ ...retryable, input: {} })).toBe(false);
    expect(canRetryOperation({ ...retryable, command_id: null })).toBe(false);
    expect(canRetryOperation(operations.find((item) => item.id === 5))).toBe(
      false,
    );
  });
});
