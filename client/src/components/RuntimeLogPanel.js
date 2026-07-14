import React, { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Space, Tag, Tooltip, Typography, message } from "antd";

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

const ERROR_PATTERNS = [
  { label: "Python error", regex: /traceback|exception|runtimeerror/i },
  { label: "missing file", regex: /no such file|not found|does not exist/i },
  { label: "memory error", regex: /out of memory|cuda.*memory|mps.*memory/i },
  { label: "failed step", regex: /failed|error/i },
];

function countMatches(text, regex) {
  return (text.match(regex) || []).length;
}

function summarizeRuntime(runtime, text) {
  const phase = runtime?.phase || "idle";
  const exitCode = runtime?.exitCode;
  const numericExitCode = Number(exitCode);
  const hasNonZeroExit =
    exitCode !== null &&
    exitCode !== undefined &&
    exitCode !== "" &&
    Number.isFinite(numericExitCode) &&
    numericExitCode !== 0;
  const firstError = ERROR_PATTERNS.find((item) => item.regex.test(text || ""));
  const warningCount = countMatches(text || "", /\bwarning\b/gi);

  if (phase === "running" || phase === "starting") {
    return {
      type: "info",
      label: phase === "starting" ? "Starting" : "Running",
      message: "The run is active. You do not need to read the log unless it fails.",
    };
  }

  if (phase === "finished" && !hasNonZeroExit && !firstError) {
    return {
      type: warningCount ? "warning" : "success",
      label: warningCount ? "Completed with warnings" : "Completed",
      message: warningCount
        ? `${warningCount} warning${warningCount === 1 ? "" : "s"} found. Outputs may still be usable.`
        : "Run completed successfully.",
    };
  }

  if (phase === "failed" || hasNonZeroExit || firstError) {
    return {
      type: "error",
      label: "Needs attention",
      message: firstError
        ? `${firstError.label} detected. Open the log if you need details.`
        : "The run exited with an error.",
    };
  }

  if (phase === "stopped") {
    return {
      type: "warning",
      label: "Stopped",
      message: "The run was stopped before completion.",
    };
  }

  return {
    type: "info",
    label: "Idle",
    message: "No run is active.",
  };
}

function RuntimeLogPanel({ title, runtime, onRefresh }) {
  const text = runtime?.text || "";
  const phase = runtime?.phase || "idle";
  const metadata = runtime?.metadata || {};
  const [showDetails, setShowDetails] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const previousPhaseRef = useRef(phase);
  const hasObservedRuntimeRef = useRef(false);
  const summary = useMemo(() => summarizeRuntime(runtime, text), [runtime, text]);

  useEffect(() => {
    if (!hasObservedRuntimeRef.current) {
      hasObservedRuntimeRef.current = true;
      previousPhaseRef.current = phase;
      return;
    }
    const previousPhase = previousPhaseRef.current;
    if (previousPhase !== phase) {
      if (phase === "finished" && summary.type === "success") {
        message.success(`${title} completed.`);
      } else if (phase === "finished" && summary.type === "warning") {
        message.warning(`${title} completed with warnings.`);
      } else if (phase === "failed" || summary.type === "error") {
        message.error(`${title} needs attention.`);
      }
    }
    previousPhaseRef.current = phase;
  }, [phase, summary.type, title]);

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
          <Tooltip
            title={`PID ${formatValue(runtime?.pid)} · Exit ${formatValue(runtime?.exitCode)} · Lines ${formatValue(runtime?.lineCount)}`}
          >
            <Typography.Text strong>{title}</Typography.Text>
          </Tooltip>
          <Tag color={phaseColors[phase] || "default"}>{phase}</Tag>
        </Space>
        <Space wrap size={8}>
          <Button
            size="small"
            type="text"
            onClick={() => setShowDetails((value) => !value)}
          >
            {showDetails ? "Hide details" : "Details"}
          </Button>
          <Button
            size="small"
            type={showLog ? "default" : "text"}
            onClick={() => setShowLog((value) => !value)}
          >
            {showLog ? "Hide log" : "Show log"}
          </Button>
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

      <div style={{ padding: "12px 16px" }}>
        <Alert
          type={summary.type}
          showIcon
          message={summary.label}
          description={summary.message}
          style={{ marginBottom: showDetails || showLog ? 12 : 0 }}
        />

        {showDetails && (
          <>
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
          </>
        )}

        {showLog && (
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
        )}
      </div>
    </div>
  );
}

export default RuntimeLogPanel;
