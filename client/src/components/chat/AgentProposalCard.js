import React, { useMemo, useState } from "react";
import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { Button, Input, Space, Tag, Typography } from "antd";

import { getProposalCardContent } from "../../contexts/workflow/proposalCardConfig";
import { getApprovalMeta } from "../../design/workflowDesignSystem";
import AgentBadge, {
  getAgentBorderStyles,
  getAgentVisual,
} from "./AgentVisuals";

const { Text } = Typography;

const asObject = (value) =>
  value && typeof value === "object" && !Array.isArray(value) ? value : null;

const toList = (value) => (Array.isArray(value) ? value : []);

const asText = (value) => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.trim();
  return String(value);
};

const collectArtifacts = (artifacts = []) =>
  toList(artifacts)
    .map((artifact, index) => {
      if (typeof artifact === "string") {
        return artifact;
      }
      if (!artifact || typeof artifact !== "object") return null;
      const fallbackKind =
        artifact.path !== undefined
          ? "path"
          : artifact.name !== undefined
            ? "name"
            : artifact.id !== undefined
              ? "id"
              : artifact.uri !== undefined
                ? "uri"
                : null;
      const kind = asText(
        artifact.kind || artifact.artifact_type || artifact.type,
      );
      const identifier = asText(
        artifact.path ||
          artifact.label ||
          artifact.name ||
          artifact.uri ||
          artifact.value ||
          artifact.id,
      );
      const prefix = kind || fallbackKind || "artifact";
      return identifier
        ? `${prefix}: ${identifier}`
        : `${prefix} (#${index + 1})`;
    })
    .filter(Boolean);

const collectTracedFacts = (trace = []) =>
  toList(trace)
    .filter((item) =>
      ["checked", "inferred", "proposed", "policy"].includes(
        item.category || item.status || item.state || "checked",
      ),
    )
    .map((item) => {
      const label = asText(item.label) || "Operational check";
      const detail = asText(item.detail);
      return detail ? `${label}: ${detail}` : label;
    });

const collectPolicyLines = (proposal = {}, actionCard = {}) => {
  const policy =
    asObject(proposal.policy_decision) || asObject(actionCard.policy_decision);
  const lines = [];

  const decision = asText(
    policy?.decision ||
      proposal.decision ||
      actionCard.policyDecision ||
      actionCard.decision,
  );
  if (decision) {
    lines.push(`Decision: ${decision}`);
  }

  const requiresApproval =
    policy && typeof policy.requires_approval === "boolean"
      ? policy.requires_approval
      : typeof actionCard.requires_approval === "boolean"
        ? actionCard.requires_approval
        : typeof actionCard.requiresApproval === "boolean"
          ? actionCard.requiresApproval
          : typeof proposal.requires_approval === "boolean"
            ? proposal.requires_approval
            : typeof proposal.requiresApproval === "boolean"
              ? proposal.requiresApproval
              : null;
  if (typeof requiresApproval === "boolean") {
    lines.push(requiresApproval ? "Approval required" : "No approval required");
  }

  const blockers = [
    ...toList(policy?.blocking_reasons),
    ...toList(actionCard.blocking_reasons),
  ].filter(Boolean);
  if (blockers.length) {
    lines.push(
      `Blockers: ${blockers
        .map(
          (blocker) => blocker?.reason || blocker?.message || String(blocker),
        )
        .join(", ")}`,
    );
  }
  const blockedBy = toList(actionCard.blockers).filter(Boolean);
  if (blockedBy.length) {
    lines.push(`Blocked by: ${blockedBy.join(", ")}`);
  }

  const riskLevel = asText(
    actionCard.risk_level ||
      actionCard.riskLevel ||
      proposal.risk_level ||
      proposal.riskLevel,
  );
  if (riskLevel) {
    lines.push(`Risk level: ${riskLevel}`);
  }

  const reason = asText(
    policy?.reason || actionCard.approval_reason || proposal.approval_reason,
  );
  if (reason) {
    lines.push(reason);
  }

  const reasonCode = asText(policy?.reason_code || proposal.reason_code);
  if (reasonCode) {
    lines.push(`Reason code: ${reasonCode}`);
  }

  return lines.filter(Boolean);
};

const collectStatusLines = (proposal = {}) => {
  const status = asText(proposal.approval_status || "not_required");
  const statusMeta = getApprovalMeta(status);
  const lines = [`Approval status: ${statusMeta.label}`];

  const executionStatus = asText(
    proposal.execution_status ||
      proposal.executionStatus ||
      proposal.execution_state ||
      proposal.executionState,
  );
  if (executionStatus) {
    lines.push(`Execution status: ${executionStatus}`);
  }
  const executionReason = asText(
    proposal.execution_reason || proposal.executionReason,
  );
  if (executionReason) {
    lines.push(`Execution reason: ${executionReason}`);
  }
  return lines;
};

const collectProjectMemoryLines = (proposal = {}, actionCard = {}) => {
  const updates =
    asObject(actionCard.project_memory_update) ||
    asObject(actionCard.project_context_update) ||
    asObject(proposal.project_memory_update) ||
    asObject(proposal.project_memory) ||
    asObject(proposal.project_context_update);

  if (!updates) {
    return [];
  }

  return Object.entries(updates)
    .filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    )
    .map(([key, value]) => {
      if (typeof value === "object") {
        return `${key}: ${asText(JSON.stringify(value))}`;
      }
      return `${key}: ${asText(value)}`;
    });
};

function ProposalTraceLine({ title, lines }) {
  if (!lines.length) return null;

  return (
    <div className="workflow-proposal-card__trace-block">
      <Text className="workflow-proposal-card__trace-block-title" strong>
        {title}
      </Text>
      <div className="workflow-proposal-card__trace-block-body">
        {lines.map((line, index) => (
          <Text
            key={`${title}-${index}`}
            className="workflow-proposal-card__trace-line"
            type="secondary"
          >
            {line}
          </Text>
        ))}
      </div>
    </div>
  );
}

function AgentProposalCard({
  proposal,
  onApprove,
  onReject,
  disabled = false,
  trace = [],
}) {
  const content = getProposalCardContent(proposal || {});
  const approvalMeta = getApprovalMeta(proposal?.approval_status || "pending");
  const isPending = (proposal?.approval_status || "pending") === "pending";
  const actionCard = useMemo(
    () => asObject(proposal?.action_card) || {},
    [proposal?.action_card],
  );
  const specialist = useMemo(
    () =>
      asObject(proposal?.specialist_agent) ||
      asObject(actionCard?.specialist_agent) ||
      {},
    [actionCard?.specialist_agent, proposal?.specialist_agent],
  );
  const agentVisual = getAgentVisual({
    ...specialist,
    agent_label: proposal?.agent_label,
    agent_color: proposal?.agent_color,
    agent_icon_key: proposal?.agent_icon_key,
    agent_border_style: proposal?.agent_border_style,
  });

  const traceItems = useMemo(
    () => (Array.isArray(trace) ? trace : []),
    [trace],
  );
  const fields = useMemo(() => content.fields || [], [content.fields]);
  const editableFields = useMemo(
    () => fields.filter((field) => field.editable),
    [fields],
  );

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() =>
    editableFields.reduce(
      (acc, field) => ({
        ...acc,
        [field.key]: field.rawValue ?? proposal?.[field.key] ?? "",
      }),
      {},
    ),
  );
  const [traceOpen, setTraceOpen] = useState(false);

  const hasEditableFields = editableFields.length > 0;
  const changedFields = useMemo(() => {
    if (!hasEditableFields) return {};
    return editableFields.reduce((acc, field) => {
      const original = field.rawValue ?? proposal?.[field.key] ?? "";
      const nextValue = draft[field.key] ?? "";
      if (String(nextValue) !== String(original)) {
        acc[field.key] = nextValue;
      }
      return acc;
    }, {});
  }, [draft, editableFields, hasEditableFields, proposal]);

  const traceSections = useMemo(() => {
    const inspectedFacts = [
      ...collectTracedFacts(traceItems),
      ...(asText(actionCard.inspected_facts)
        ? [asText(actionCard.inspected_facts)]
        : []),
      ...(asText(proposal.inspected_facts)
        ? [asText(proposal.inspected_facts)]
        : []),
    ].filter(Boolean);

    const policyLines = collectPolicyLines(proposal, actionCard);
    const statusLines = collectStatusLines(proposal);
    const artifactLines = [
      ...collectArtifacts(actionCard.input_artifacts).map(
        (item) => `Input · ${item}`,
      ),
      ...collectArtifacts(actionCard.output_artifacts).map(
        (item) => `Output · ${item}`,
      ),
    ];
    const projectMemoryLines = collectProjectMemoryLines(proposal, actionCard);

    return [
      {
        title: "Inspected facts",
        lines: inspectedFacts,
      },
      {
        title: "Policy decision",
        lines: policyLines,
      },
      {
        title: "Approval / execution status",
        lines: statusLines,
      },
      {
        title: "Affected artifacts",
        lines: artifactLines,
      },
      {
        title: "Project-memory updates",
        lines: projectMemoryLines,
      },
    ].filter((section) => section.lines.length > 0);
  }, [actionCard, proposal, traceItems]);

  const hasChanges = Object.keys(changedFields).length > 0;

  const resetDraft = () => {
    setDraft(
      editableFields.reduce(
        (acc, field) => ({
          ...acc,
          [field.key]: field.rawValue ?? proposal?.[field.key] ?? "",
        }),
        {},
      ),
    );
  };

  const beginEditing = () => {
    if (!isPending || disabled) return;
    setEditing(true);
  };

  const endEditing = () => {
    setEditing(false);
    resetDraft();
  };

  const handleEditToggle = () => {
    if (!editing) {
      beginEditing();
      return;
    }
    endEditing();
  };

  const setFieldValue = (field, value) => {
    setDraft((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const approveLabel = hasChanges ? "Approve with edits" : "Approve";

  return (
    <section
      aria-label={`proposal-${content.type}`}
      className={`workflow-proposal-card workflow-tone-${approvalMeta.tone}`}
      style={getAgentBorderStyles(agentVisual.borderStyle, agentVisual.color)}
    >
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <div className="workflow-proposal-card__header">
          <Text className="workflow-proposal-card__title" strong>
            {content.title}
          </Text>
          <span className="workflow-proposal-card__agent-badge">
            <AgentBadge agent={agentVisual} />
          </span>
          <Tag
            className="workflow-proposal-card__type-tag"
            style={{ margin: 0 }}
          >
            {content.type}
          </Tag>
          <Tag
            className="workflow-proposal-card__status-tag"
            color={approvalMeta.color}
            style={{ margin: 0 }}
          >
            {approvalMeta.label}
          </Tag>
        </div>
        <Text
          className="workflow-proposal-card__rationale"
          style={{
            fontSize: 12,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {content.rationale}
        </Text>
        {content.fields?.length > 0 && (
          <div className="workflow-proposal-card__fields">
            {content.fields.map((field) => (
              <React.Fragment key={field.key}>
                <Text
                  type="secondary"
                  className="workflow-proposal-card__field-label"
                >
                  {field.label}
                </Text>
                {editing && isPending ? (
                  field.editable ? (
                    <Input.TextArea
                      autoSize={{ minRows: 1, maxRows: 3 }}
                      value={draft[field.key] ?? ""}
                      onChange={(event) =>
                        setFieldValue(field.key, event.target.value)
                      }
                      style={{ fontSize: 11 }}
                      aria-label={`Edit ${field.label}`}
                    />
                  ) : (
                    <Text
                      className="workflow-proposal-card__field-value"
                      style={{
                        fontSize: 11,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                      }}
                    >
                      {field.value}
                    </Text>
                  )
                ) : (
                  <Text
                    className={
                      field.editable
                        ? `workflow-proposal-card__field-value${
                            isPending
                              ? " workflow-proposal-card__field-value--editable"
                              : ""
                          }`
                        : "workflow-proposal-card__field-value"
                    }
                    style={{
                      fontSize: 11,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                    role={field.editable ? "button" : undefined}
                    tabIndex={field.editable && isPending ? 0 : -1}
                    onClick={field.editable ? beginEditing : undefined}
                    onKeyDown={
                      field.editable
                        ? (event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              beginEditing();
                            }
                          }
                        : undefined
                    }
                    aria-label={
                      field.editable ? `Edit ${field.label}` : undefined
                    }
                  >
                    {field.value}
                  </Text>
                )}
              </React.Fragment>
            ))}
          </div>
        )}

        {traceSections.length > 0 && (
          <div className="workflow-proposal-card__trace">
            <Button
              type="text"
              size="small"
              icon={traceOpen ? <DownOutlined /> : <RightOutlined />}
              onClick={() => setTraceOpen((value) => !value)}
              style={{ paddingInline: 0, height: 24 }}
            >
              Operational trace
            </Button>
            {traceOpen && (
              <div className="workflow-proposal-card__trace-body">
                {traceSections.map((section) => (
                  <ProposalTraceLine
                    key={section.title}
                    title={section.title}
                    lines={section.lines}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        <Space size="small">
          <Button
            type="primary"
            size="small"
            onClick={() => onApprove?.(proposal, changedFields)}
            disabled={disabled || !isPending}
          >
            {approveLabel}
          </Button>
          {hasEditableFields && isPending && (
            <Button size="small" onClick={handleEditToggle} disabled={disabled}>
              {editing ? "Cancel edits" : "Edit details"}
            </Button>
          )}
          <Button
            size="small"
            onClick={() => onReject?.(proposal)}
            disabled={disabled || !isPending}
          >
            Reject
          </Button>
        </Space>
      </Space>
    </section>
  );
}

export default AgentProposalCard;
