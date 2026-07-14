import React, { useState } from "react";
import { Button, Typography } from "antd";
import { DownOutlined, RightOutlined } from "@ant-design/icons";
import AgentBadge, { getAgentBorderStyles, getAgentVisual } from "./AgentVisuals";

const { Text } = Typography;

const CATEGORY_LABELS = {
  checked: "Checked",
  inferred: "Inferred",
  proposed: "Proposed",
  blocked_by: "Blocked",
};

const TRACE_SECTION_LABELS = {
  checked: "Inspected facts",
  inferred: "Inferred context",
  proposed: "Decision",
  blocked_by: "Policy gate",
};

const getCategory = (item = {}) => item.category || item.status || "checked";

function summarizeTraceSections(traceItems = []) {
  const grouped = {};
  traceItems.forEach((item) => {
    const normalizedCategory = getCategory(item);
    if (!grouped[normalizedCategory]) grouped[normalizedCategory] = [];
    grouped[normalizedCategory].push(item);
  });
  return Object.keys(TRACE_SECTION_LABELS)
    .map((category) => ({
      key: category,
      label: TRACE_SECTION_LABELS[category],
      items: grouped[category] || [],
    }))
    .concat(
      Object.keys(grouped)
        .filter((key) => !(key in TRACE_SECTION_LABELS))
        .map((key) => ({
          key,
          label: CATEGORY_LABELS[key] || key,
          items: grouped[key] || [],
        })),
    )
    .filter((section) => section.items.length > 0);
}

function AssistantTrace({ trace = [] }) {
  const [open, setOpen] = useState(false);
  const items = Array.isArray(trace) ? trace.filter(Boolean) : [];
  if (!items.length) return null;
  const traceSections = summarizeTraceSections(items);

  return (
    <div style={{ marginTop: 2 }}>
      <Button
        type="text"
        size="small"
        icon={open ? <DownOutlined /> : <RightOutlined />}
        onClick={() => setOpen((value) => !value)}
        style={{
          height: 24,
          paddingInline: 0,
          color: "#6b7280",
          fontSize: 12,
          fontWeight: 500,
        }}
      >
        Operational trace
      </Button>
      {open && (
        <div className="assistant-trace__panel">
          {traceSections.map((section) => (
            <div key={section.key} className="assistant-trace__section">
              <Text style={{ fontSize: 11 }} strong>
                {section.label}
              </Text>
              <div className="assistant-trace__items">
                {section.items.map((item, index) => (
                  <div
                    key={`${item.label || "trace"}-${section.key}-${index}`}
                    className="assistant-trace__item"
                    style={{
                      ...getAgentBorderStyles(item.agent_border_style, item.agent_color, 3),
                    }}
                  >
                    <div
                      style={{
                        alignItems: "center",
                        display: "flex",
                        gap: 6,
                      }}
                    >
                      <AgentBadge agent={getAgentVisual(item)} compact />
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {CATEGORY_LABELS[getCategory(item)] || getCategory(item) || "Step"}
                      </Text>
                      <Text style={{ color: "#374151", fontSize: 11 }}>
                        {item.label || "Operational step"}
                      </Text>
                    </div>
                    {item.detail && (
                      <Text type="secondary" style={{ display: "block", fontSize: 11 }}>
                        {item.detail}
                      </Text>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AssistantTrace;
