import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Empty,
  Popconfirm,
  Progress,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { RedoOutlined, ReloadOutlined, StopOutlined } from "@ant-design/icons";
import {
  cancelWorkflowOperation,
  listWorkflowOperations,
  runWorkflowCommand,
} from "../../api";
import { getApiErrorMessage } from "../../errors/apiError";
import { useWorkflow } from "../../contexts/WorkflowContext";
import "./WorkflowOperationsPanel.css";

const { Text } = Typography;
const ACTIVE_OPERATION_STATUSES = new Set(["queued", "running"]);
const CANCELLABLE_OPERATION_STATUSES = new Set(["queued", "running"]);
const OPERATION_POLL_INTERVAL_MS = 2500;

const STATUS_CONFIG = {
  queued: { label: "Queued", color: "default" },
  running: { label: "Running", color: "processing" },
  succeeded: { label: "Succeeded", color: "success" },
  failed: { label: "Failed", color: "error" },
  cancelled: { label: "Cancelled", color: "warning" },
};

export const hasActiveOperations = (operations = []) =>
  operations.some((operation) =>
    ACTIVE_OPERATION_STATUSES.has(operation?.status),
  );

export const getOperationsRefetchInterval = (query) =>
  hasActiveOperations(query?.state?.data) ? OPERATION_POLL_INTERVAL_MS : false;

export const getWorkflowOperationsQueryOptions = (
  workflowId,
  { compact = false } = {},
) => ({
  queryKey: ["workflow", workflowId, "operations"],
  queryFn: () =>
    listWorkflowOperations(workflowId, { limit: compact ? 6 : 12 }),
  enabled: Boolean(workflowId),
  refetchInterval: getOperationsRefetchInterval,
  refetchOnReconnect: "always",
});

const hasReplayableInput = (input) =>
  Boolean(
    input &&
    typeof input === "object" &&
    !Array.isArray(input) &&
    Object.keys(input).length,
  );

export const canRetryOperation = (operation) => {
  if (operation?.status !== "failed" || !operation?.command_id) return false;

  const retry = operation.metadata?.retry;
  if (
    retry?.allowed === true &&
    retry?.kind === "workflow_command" &&
    hasReplayableInput(operation.input)
  ) {
    return true;
  }

  return Boolean(
    operation.metadata?.command_type === "start_training" &&
    operation.metadata?.execution_scope === "worker_submission" &&
    [503, 504].includes(Number(operation.error?.status_code)) &&
    hasReplayableInput(operation.input),
  );
};

const operationLabel = (value) => {
  const normalized = String(value || "operation")
    .replace(/^agent_action:/, "")
    .replace(/[_:]+/g, " ")
    .trim();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
};

const operationErrorMessage = (operation) => {
  const error = operation?.error;
  if (!error) return "";
  if (typeof error === "string") return error;
  if (typeof error.detail === "string") return error.detail;
  if (typeof error.message === "string") return error.message;
  if (typeof error.error === "string") return error.error;
  return "The operation did not complete.";
};

const formatUpdatedAt = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

function OperationRow({ operation, cancelling, retrying, onCancel, onRetry }) {
  const status = STATUS_CONFIG[operation.status] || {
    label: operationLabel(operation.status),
    color: "default",
  };
  const cancellationRequested = Boolean(operation.cancellation_requested_at);
  const cancellationPending =
    cancellationRequested && operation.status === "running";
  const cancellationAcknowledged =
    cancellationRequested && operation.status === "cancelled";
  const canCancel =
    CANCELLABLE_OPERATION_STATUSES.has(operation.status) &&
    !cancellationRequested;
  const canRetry = canRetryOperation(operation);
  const progress = Number(operation.progress);
  const hasProgress =
    operation.progress !== null &&
    operation.progress !== undefined &&
    Number.isFinite(progress);
  const errorMessage = operationErrorMessage(operation);

  return (
    <div className="workflow-operation-row" data-status={operation.status}>
      <div className="workflow-operation-row__main">
        <div className="workflow-operation-row__heading">
          <Text strong>{operationLabel(operation.operation_type)}</Text>
          <Space size={4} wrap>
            <Tag color={status.color}>{status.label}</Tag>
            {cancellationPending && (
              <Tag color="warning">Cancellation requested</Tag>
            )}
            {cancellationAcknowledged && (
              <Tag color="default">Cancellation acknowledged</Tag>
            )}
          </Space>
        </div>

        <div className="workflow-operation-row__metadata">
          <Text type="secondary" className="workflow-operation-row__reference">
            Ref {operation.correlation_id || `operation-${operation.id}`}
          </Text>
          {formatUpdatedAt(operation.updated_at) && (
            <Text type="secondary">
              Updated {formatUpdatedAt(operation.updated_at)}
            </Text>
          )}
          {operation.attempt_count > 0 && (
            <Text type="secondary">Attempt {operation.attempt_count}</Text>
          )}
        </div>

        {hasProgress && operation.status === "running" && (
          <Progress
            percent={Math.round(Math.max(0, Math.min(1, progress)) * 100)}
            size="small"
            status={cancellationPending ? "exception" : "active"}
            aria-label={`${operationLabel(operation.operation_type)} progress`}
          />
        )}

        {errorMessage && operation.status === "failed" && (
          <Text type="danger" className="workflow-operation-row__error">
            {errorMessage}
          </Text>
        )}
      </div>

      {(canCancel || canRetry) && (
        <Space size={6} className="workflow-operation-row__actions">
          {canRetry && (
            <Button
              size="small"
              icon={<RedoOutlined />}
              loading={retrying}
              onClick={() => onRetry(operation)}
            >
              Retry
            </Button>
          )}
          {canCancel && (
            <Popconfirm
              title="Cancel this operation?"
              description={
                operation.status === "running"
                  ? "The worker will stop at its next cancellation checkpoint."
                  : "This queued operation will not start."
              }
              okText="Cancel operation"
              cancelText="Keep running"
              okButtonProps={{ danger: true }}
              onConfirm={() => onCancel(operation)}
            >
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                loading={cancelling}
              >
                Cancel
              </Button>
            </Popconfirm>
          )}
        </Space>
      )}
    </div>
  );
}

function WorkflowOperationsPanel({ compact = false }) {
  const workflow = useWorkflow()?.workflow;
  const workflowId = workflow?.id;
  const queryClient = useQueryClient();
  const queryKey = ["workflow", workflowId, "operations"];
  const [actionError, setActionError] = useState("");

  const operationsQuery = useQuery(
    getWorkflowOperationsQueryOptions(workflowId, { compact }),
  );

  const refreshOperations = () => {
    setActionError("");
    operationsQuery.refetch();
  };

  const updateOperation = (updatedOperation) => {
    queryClient.setQueryData(queryKey, (current = []) =>
      current.map((operation) =>
        operation.id === updatedOperation.id ? updatedOperation : operation,
      ),
    );
  };

  const cancelMutation = useMutation({
    mutationFn: (operation) =>
      cancelWorkflowOperation(
        workflowId,
        operation.id,
        "Cancelled from the workflow operations panel.",
      ),
    onMutate: () => setActionError(""),
    onSuccess: (operation) => {
      updateOperation(operation);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => setActionError(getApiErrorMessage(error)),
  });

  const retryMutation = useMutation({
    mutationFn: (operation) =>
      runWorkflowCommand(workflowId, operation.command_id),
    onMutate: () => setActionError(""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    onError: (error) => setActionError(getApiErrorMessage(error)),
  });

  if (!workflowId) return null;

  const operations = operationsQuery.data || [];
  const activeCount = operations.filter((operation) =>
    ACTIVE_OPERATION_STATUSES.has(operation.status),
  ).length;

  return (
    <Card
      size={compact ? "small" : "default"}
      title={
        <Space size={6} wrap>
          <span>Operations</span>
          {activeCount > 0 && (
            <Tag color="processing">{activeCount} active</Tag>
          )}
        </Space>
      }
      extra={
        <Tooltip title="Refresh operations">
          <Button
            aria-label="Refresh operations"
            size="small"
            type="text"
            icon={<ReloadOutlined />}
            onClick={refreshOperations}
            disabled={operationsQuery.isFetching}
          />
        </Tooltip>
      }
    >
      {operationsQuery.isPending ? (
        <div className="workflow-operations-panel__loading">
          <Spin size="small" />
          <Text type="secondary">Connecting to operation history</Text>
        </div>
      ) : (
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          {operationsQuery.isError && (
            <Alert
              type="warning"
              showIcon
              message="Operation history is temporarily unavailable"
              description={getApiErrorMessage(operationsQuery.error)}
              action={
                <Tooltip title="Reconnect operation history">
                  <Button
                    aria-label="Reconnect operation history"
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={refreshOperations}
                  />
                </Tooltip>
              }
            />
          )}
          {actionError && (
            <Alert
              closable
              type="error"
              showIcon
              message="Operation action failed"
              description={actionError}
              onClose={() => setActionError("")}
            />
          )}
          {operations.length ? (
            <div className="workflow-operations-panel__list">
              {operations.map((operation) => (
                <OperationRow
                  key={operation.id}
                  operation={operation}
                  cancelling={
                    cancelMutation.isPending &&
                    cancelMutation.variables?.id === operation.id
                  }
                  retrying={
                    retryMutation.isPending &&
                    retryMutation.variables?.id === operation.id
                  }
                  onCancel={cancelMutation.mutate}
                  onRetry={retryMutation.mutate}
                />
              ))}
            </div>
          ) : (
            !operationsQuery.isError && (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="No durable operations recorded"
              />
            )
          )}
          {operationsQuery.isFetching && !operationsQuery.isPending && (
            <Text
              type="secondary"
              className="workflow-operations-panel__syncing"
            >
              Syncing operation state
            </Text>
          )}
        </Space>
      )}
    </Card>
  );
}

export default WorkflowOperationsPanel;
