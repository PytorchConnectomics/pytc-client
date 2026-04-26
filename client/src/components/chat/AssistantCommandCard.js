import React, { useState } from "react";
import { Button, Tag, Typography } from "antd";

const { Text } = Typography;
const MONO_FONT =
  "'SFMono-Regular', Menlo, Monaco, Consolas, 'Liberation Mono', monospace";

const RISK_LABELS = {
  read_only: "view only",
  prefills_form: "sets form",
  loads_editor: "opens editor",
  runs_job: "runs job",
  writes_workflow_record: "writes record",
  exports_evidence: "exports",
};

function AssistantCommandCard({ command, onRun, disabled = false }) {
  const [showDetails, setShowDetails] = useState(false);
  const riskLabel = RISK_LABELS[command?.risk_level] || command?.risk_level;

  return (
    <section
      aria-label={`assistant-command-${command?.id || "unknown"}`}
      style={{
        border: "1px solid #d9d9d9",
        borderRadius: 12,
        overflow: "hidden",
        background: "#ffffff",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "10px 12px",
          borderBottom: "1px solid #f0f0f0",
          background: "#fafafa",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <Text
            strong
            style={{
              display: "block",
              fontSize: 12,
              fontFamily: MONO_FONT,
            }}
          >
            {command?.title || "App Command"}
          </Text>
          {riskLabel && (
            <Tag
              style={{
                marginTop: 4,
                marginInlineEnd: 0,
                fontSize: 11,
                lineHeight: "18px",
              }}
            >
              {riskLabel}
            </Tag>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Button
            size="small"
            type="text"
            onClick={() => setShowDetails((current) => !current)}
          >
            {showDetails ? "Hide route" : "Route"}
          </Button>
          <Button
            size="small"
            type="primary"
            onClick={() => onRun?.(command)}
            disabled={disabled}
          >
            {command?.run_label || "Execute"}
          </Button>
        </div>
      </div>
      <div style={{ padding: "10px 12px" }}>
        {command?.description && (
          <Text
            style={{
              display: "block",
              fontSize: 12,
            }}
            type="secondary"
          >
            {command.description}
          </Text>
        )}
        {showDetails && (
          <pre
            style={{
              margin: "10px 0 0",
              background: "#111827",
              color: "#f3f4f6",
              padding: 12,
              borderRadius: 8,
              fontSize: 12,
              overflowX: "auto",
              fontFamily: MONO_FONT,
              lineHeight: 1.6,
            }}
          >
            <code>{command?.command}</code>
          </pre>
        )}
      </div>
    </section>
  );
}

export default AssistantCommandCard;
