import React from "react";
import { Tag } from "antd";
import {
  BarChartOutlined,
  BugOutlined,
  ExperimentOutlined,
  EyeOutlined,
  FileDoneOutlined,
  FolderOpenOutlined,
  ProjectOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

const ICONS = {
  bar_chart: BarChartOutlined,
  bug: BugOutlined,
  experiment: ExperimentOutlined,
  eye: EyeOutlined,
  file_done: FileDoneOutlined,
  folder: FolderOpenOutlined,
  project: ProjectOutlined,
  thunderbolt: ThunderboltOutlined,
};

const ALLOWED_BORDER_STYLES = new Set([
  "solid",
  "dotted",
  "double",
  "dashed",
  "thick",
  "dashdot",
  "top",
  "rail",
]);

const normalizeAgentText = (value) => {
  if (typeof value !== "string") return "";
  return value.trim();
};

const normalizeAgentColor = (value) => {
  const text = normalizeAgentText(value);
  if (!text) return DEFAULT_AGENT_VISUAL.color;
  return text;
};

const normalizeAgentIconKey = (value) => {
  const text = normalizeAgentText(value);
  return ICONS[text] ? text : DEFAULT_AGENT_VISUAL.icon_key;
};

const normalizeBorderStyle = (value) => {
  const text = normalizeAgentText(value).toLowerCase();
  return ALLOWED_BORDER_STYLES.has(text)
    ? text
    : DEFAULT_AGENT_VISUAL.border_style;
};

export const DEFAULT_AGENT_VISUAL = {
  label: "Project Manager",
  shortLabel: "PM",
  color: "#111827",
  icon_key: "project",
  border_style: "solid",
};

export function getAgentVisual(agent = {}) {
  const explicitLabel =
    normalizeAgentText(agent.agent_label) || normalizeAgentText(agent.label);
  const shortLabel =
    normalizeAgentText(agent.agent_short_label) ||
    normalizeAgentText(agent.short_label) ||
    normalizeAgentText(agent.shortLabel);

  return {
    label: explicitLabel || DEFAULT_AGENT_VISUAL.label,
    shortLabel: shortLabel || explicitLabel || DEFAULT_AGENT_VISUAL.shortLabel,
    color: normalizeAgentColor(agent.agent_color || agent.color),
    iconKey: normalizeAgentIconKey(agent.agent_icon_key || agent.icon_key),
    borderStyle: normalizeBorderStyle(
      agent.agent_border_style || agent.border_style,
    ),
  };
}

export function getAgentBorderStyles(borderStyle, color, width = 4) {
  const accent = color || DEFAULT_AGENT_VISUAL.color;
  const base = {
    borderLeft: `${width}px solid ${accent}`,
  };

  switch (borderStyle) {
    case "dotted":
      return { borderLeft: `${width}px dotted ${accent}` };
    case "double":
      return { borderLeft: `${Math.max(width + 1, 5)}px double ${accent}` };
    case "dashed":
      return { borderLeft: `${width}px dashed ${accent}` };
    case "thick":
      return { borderLeft: `${Math.max(width + 2, 6)}px solid ${accent}` };
    case "dashdot":
      return {
        borderLeft: `${width}px solid ${accent}`,
        borderTop: `2px dashed ${accent}`,
      };
    case "top":
      return {
        borderLeft: `${width}px solid ${accent}`,
        borderTop: `3px solid ${accent}`,
      };
    case "rail":
      return {
        borderLeft: `${width}px solid ${accent}`,
        boxShadow: `inset ${width + 2}px 0 0 rgba(0, 166, 166, 0.14)`,
      };
    default:
      return base;
  }
}

function AgentIcon({ iconKey }) {
  const Icon = ICONS[iconKey] || ICONS.project;
  return <Icon aria-hidden="true" />;
}

function AgentBadge({
  agent,
  label,
  color,
  iconKey,
  compact = false,
  labelMode = "short",
}) {
  const visual = getAgentVisual({
    ...(agent || {}),
    label,
    color,
    icon_key: iconKey,
  });
  const displayLabel =
    labelMode === "full" ? visual.label : visual.shortLabel || visual.label;

  return (
    <Tag
      color={visual.color}
      style={{
        alignItems: "center",
        display: "inline-flex",
        flexShrink: 0,
        gap: 4,
        lineHeight: compact ? "16px" : "18px",
        marginInlineEnd: 0,
        maxWidth: "none",
        overflow: "visible",
        whiteSpace: "normal",
        fontSize: compact ? 10 : 11,
      }}
      title={visual.label}
    >
      <AgentIcon iconKey={visual.iconKey} />
      <span
        style={{
          overflowWrap: "anywhere",
          whiteSpace: "normal",
          minWidth: 0,
        }}
      >
        {displayLabel}
      </span>
    </Tag>
  );
}

export default AgentBadge;
