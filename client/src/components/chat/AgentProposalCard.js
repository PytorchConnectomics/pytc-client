import React from "react";
import { Button, Space, Tag, Typography } from "antd";

import { getProposalCardContent } from "../../contexts/workflow/proposalCardConfig";
import { getApprovalMeta } from "../../design/workflowDesignSystem";

const { Text } = Typography;

function AgentProposalCard({ proposal, onApprove, onReject, disabled = false }) {
  const content = getProposalCardContent(proposal || {});
  const approvalMeta = getApprovalMeta(proposal?.approval_status || "pending");

  return (
    <section
      aria-label={`proposal-${content.type}`}
      className={`workflow-proposal-card workflow-tone-${approvalMeta.tone}`}
    >
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space size="small" wrap>
          <Text strong style={{ fontSize: 12 }}>
            {content.title}
          </Text>
          <Tag style={{ margin: 0 }}>{content.type}</Tag>
          <Tag color={approvalMeta.color} style={{ margin: 0 }}>
            {approvalMeta.label}
          </Tag>
        </Space>
        <Text style={{ fontSize: 12 }}>{content.rationale}</Text>
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
                <Text style={{ fontSize: 11 }}>{field.value}</Text>
              </React.Fragment>
            ))}
          </div>
        )}
        <Space size="small">
          <Button
            type="primary"
            size="small"
            onClick={() => onApprove?.(proposal)}
            disabled={disabled}
          >
            Approve
          </Button>
          <Button size="small" onClick={() => onReject?.(proposal)} disabled={disabled}>
            Reject
          </Button>
        </Space>
      </Space>
    </section>
  );
}

export default AgentProposalCard;
