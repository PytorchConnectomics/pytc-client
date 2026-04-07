import React from "react";
import { Alert, Button, Space, Tag, Typography, message } from "antd";

const phaseColors = {
  idle: "default",
  starting: "processing",
  running: "processing",
  finished: "success",
  failed: "error",
  stopped: "warning",
};

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function RuntimeLogPanel({ title, runtime, onRefresh }) {
  const text = runtime?.text || "";
  const phase = runtime?.phase || "idle";
  const metadata = runtime?.metadata || {};

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text || "");
      message.success(`${title} log copied.`);
    } catch (error) {
      message.error(`Failed to copy ${title.toLowerCase()} log.`);
    }
  };

  return (
    <div
      style={{
        marginTop: 16,
        border: "1px solid #d9d9d9",
        borderRadius: 8,
        overflow: "hidden",
        background: "#fafafa",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 16px",
          borderBottom: "1px solid #f0f0f0",
          background: "#fff",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <Space wrap size={8}>
          <Typography.Text strong>{title}</Typography.Text>
          <Tag color={phaseColors[phase] || "default"}>{phase}</Tag>
          <Typography.Text type="secondary">
            PID {formatValue(runtime?.pid)}
          </Typography.Text>
          <Typography.Text type="secondary">
            Exit {formatValue(runtime?.exitCode)}
          </Typography.Text>
          <Typography.Text type="secondary">
            Lines {formatValue(runtime?.lineCount)}
          </Typography.Text>
        </Space>
        <Space wrap size={8}>
          <Button size="small" onClick={onRefresh}>
            Refresh
          </Button>
          <Button size="small" onClick={handleCopy} disabled={!text}>
            Copy Log
          </Button>
        </Space>
      </div>

      {runtime?.lastError && (
        <div style={{ padding: "12px 16px 0 16px" }}>
          <Alert
            type="error"
            showIcon
            message={runtime.lastError}
            style={{ marginBottom: 12 }}
          />
        </div>
      )}

      <div style={{ padding: "0 16px 12px 16px" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 8,
            marginBottom: 12,
            fontSize: 12,
            color: "#595959",
          }}
        >
          <div>Started: {formatValue(runtime?.startedAt)}</div>
          <div>Ended: {formatValue(runtime?.endedAt)}</div>
          <div>Updated: {formatValue(runtime?.lastUpdatedAt)}</div>
          <div>Config path: {formatValue(runtime?.configPath)}</div>
          <div>Config origin: {formatValue(runtime?.configOriginPath)}</div>
          <div>Output path: {formatValue(metadata.outputPath)}</div>
          <div>Checkpoint: {formatValue(metadata.checkpointPath)}</div>
          <div>Log path: {formatValue(metadata.logPath)}</div>
        </div>

        {runtime?.command && (
          <div
            style={{
              marginBottom: 12,
              padding: "8px 10px",
              borderRadius: 6,
              background: "#fff",
              border: "1px solid #f0f0f0",
              fontFamily:
                'ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace',
              fontSize: 12,
              color: "#262626",
              wordBreak: "break-word",
            }}
          >
            {runtime.command}
          </div>
        )}

        <pre
          style={{
            margin: 0,
            minHeight: 220,
            maxHeight: 420,
            overflow: "auto",
            padding: 12,
            borderRadius: 6,
            background: "#111827",
            color: "#f3f4f6",
            fontSize: 12,
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontFamily:
              'ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace',
          }}
        >
          {text || "No runtime logs captured yet."}
        </pre>
      </div>
    </div>
  );
}

export default RuntimeLogPanel;
