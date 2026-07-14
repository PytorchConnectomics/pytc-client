import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Space, Spin, Tag, Typography, message } from "antd";
import { getTensorboardStatus, startTensorboard } from "../api";
import WorkflowEvidencePanel from "../components/workflow/WorkflowEvidencePanel";

const phaseColors = {
  idle: "default",
  starting: "processing",
  running: "success",
  finished: "default",
  failed: "error",
  stopped: "warning",
};

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function Monitoring() {
  const [tensorboardStatus, setTensorboardStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const loadTensorboardStatus = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
    }
    try {
      const status = await getTensorboardStatus();
      setTensorboardStatus(status);
    } catch (error) {
      console.error("Error loading TensorBoard status:", error);
      if (!silent) {
        message.error(
          error.message || "Failed to load TensorBoard monitoring status.",
        );
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadTensorboardStatus();
    const intervalId = setInterval(() => {
      loadTensorboardStatus({ silent: true });
    }, 3000);
    return () => clearInterval(intervalId);
  }, [loadTensorboardStatus]);

  const handleStartTensorboard = async () => {
    try {
      setStarting(true);
      const response = await startTensorboard();
      message.success(
        response?.tensorboard?.isRunning
          ? "TensorBoard is ready."
          : "TensorBoard is starting.",
      );
      await loadTensorboardStatus();
    } catch (error) {
      console.error("Error starting TensorBoard:", error);
      message.error(error.message || "Failed to start TensorBoard.");
    } finally {
      setStarting(false);
    }
  };

  const sourceEntries = useMemo(
    () => Object.entries(tensorboardStatus?.sources || {}),
    [tensorboardStatus],
  );

  const phase = tensorboardStatus?.phase || "idle";
  const isRunning = Boolean(tensorboardStatus?.isRunning);
  const hasSources = sourceEntries.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <WorkflowEvidencePanel />

      <Card>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
            alignItems: "flex-start",
          }}
        >
          <Space direction="vertical" size={4}>
            <Space wrap size={8}>
              <Typography.Text strong>TensorBoard</Typography.Text>
              <Tag color={phaseColors[phase] || "default"}>{phase}</Tag>
              <Typography.Text type="secondary">
                PID {formatValue(tensorboardStatus?.pid)}
              </Typography.Text>
              <Typography.Text type="secondary">
                Port {formatValue(tensorboardStatus?.port)}
              </Typography.Text>
            </Space>
            {tensorboardStatus?.url && (
              <Typography.Link
                href={tensorboardStatus.url}
                target="_blank"
                rel="noreferrer"
              >
                {tensorboardStatus.url}
              </Typography.Link>
            )}
          </Space>
          <Space wrap>
            <Button onClick={() => loadTensorboardStatus()} disabled={loading}>
              Refresh
            </Button>
            <Button
              type="primary"
              onClick={handleStartTensorboard}
              disabled={!hasSources}
              loading={starting}
            >
              {isRunning ? "Refresh TensorBoard" : "Start TensorBoard"}
            </Button>
          </Space>
        </div>

        {tensorboardStatus?.lastError && (
          <Alert
            style={{ marginTop: 16 }}
            type="error"
            showIcon
            message={tensorboardStatus.lastError}
          />
        )}

        <div
          style={{
            marginTop: 16,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 12,
          }}
        >
          <Card size="small" title="Process">
            <div>Started: {formatValue(tensorboardStatus?.startedAt)}</div>
            <div>Ended: {formatValue(tensorboardStatus?.endedAt)}</div>
            <div>Updated: {formatValue(tensorboardStatus?.lastUpdatedAt)}</div>
            <div>Command: {formatValue(tensorboardStatus?.command)}</div>
          </Card>
          <Card size="small" title="Watched Sources">
            {hasSources ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {sourceEntries.map(([key, source]) => (
                  <div
                    key={key}
                    style={{
                      padding: "8px 10px",
                      border: "1px solid #f0f0f0",
                      borderRadius: 8,
                      background: "#fafafa",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{source.name}</div>
                    <div style={{ wordBreak: "break-word", color: "#595959" }}>
                      {source.path}
                    </div>
                    <div style={{ color: source.exists ? "#389e0d" : "#d46b08" }}>
                      {source.exists ? "Directory ready" : "Directory missing"}
                    </div>
                  </div>
                ))}
              </Space>
            ) : (
              <Typography.Text type="secondary">
                No training or inference output directories have been registered yet.
              </Typography.Text>
            )}
          </Card>
        </div>
      </Card>

      <Card bodyStyle={{ padding: 12 }}>
        {loading && !tensorboardStatus ? (
          <div
            style={{
              minHeight: 640,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Spin tip="Loading TensorBoard status..." />
          </div>
        ) : isRunning && tensorboardStatus?.url ? (
          <iframe
            title="TensorBoard Display"
            width="100%"
            height="800"
            frameBorder="0"
            src={tensorboardStatus.url}
            style={{
              border: "1px solid #f0f0f0",
              borderRadius: 10,
              minHeight: 800,
              background: "#fff",
            }}
          />
        ) : (
          <Alert
            type={hasSources ? "warning" : "info"}
            showIcon
            message={hasSources ? "TensorBoard is stopped." : "No log directory yet."}
          />
        )}
      </Card>
    </div>
  );
}

export default Monitoring;
