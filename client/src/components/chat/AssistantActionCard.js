import React from "react";
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

function AssistantActionCard({ action, onRun, disabled = false }) {
  const buttonType = action?.variant === "primary" ? "primary" : "default";
  const riskLabel = RISK_LABELS[action?.risk_level] || action?.risk_level;
  const isDisabled = disabled || Boolean(action?.disabled_reason);

  return (
    <section
      aria-label={`assistant-action-${action?.id || "unknown"}`}
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: 12,
        background: "#fbfbfa",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Text
              strong
              style={{ fontSize: 12, display: "block", fontFamily: MONO_FONT }}
            >
              {action?.label || "Action"}
            </Text>
            {riskLabel && (
              <Tag
                style={{
                  marginInlineEnd: 0,
                  fontSize: 11,
                  lineHeight: "18px",
                }}
              >
                {riskLabel}
              </Tag>
            )}
          </div>
          {action?.description && (
            <Text
              type="secondary"
              style={{ fontSize: 12, display: "block", marginTop: 4 }}
            >
              {action.description}
            </Text>
          )}
          {action?.disabled_reason && (
            <Text type="danger" style={{ fontSize: 12, display: "block" }}>
              {action.disabled_reason}
            </Text>
          )}
        </div>
        <Button
          size="small"
          type={buttonType}
          onClick={() => onRun?.(action)}
          disabled={isDisabled}
          style={{ flexShrink: 0 }}
        >
          {action?.run_label || "Run in app"}
        </Button>
      </div>
    </section>
  );
}

export default AssistantActionCard;
