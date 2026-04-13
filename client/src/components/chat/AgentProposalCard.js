import React from "react";
import { Button, Space, Tag, Typography } from "antd";

import { getProposalCardContent } from "../../contexts/workflow/proposalCardConfig";

const { Text } = Typography;

function AgentProposalCard({ proposal, onApprove, onReject, disabled = false }) {
  const content = getProposalCardContent(proposal || {});

  return (
    <section
      aria-label={`proposal-${content.type}`}
      style={{
        border: "1px solid #d9d9d9",
        borderRadius: 6,
        padding: 10,
        background: "#fff",
        marginTop: 6,
      }}
    >
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space size="small" wrap>
          <Text strong style={{ fontSize: 12 }}>
            {content.title}
          </Text>
          <Tag style={{ margin: 0 }}>{content.type}</Tag>
        </Space>
        <Text style={{ fontSize: 12 }}>{content.rationale}</Text>
        {content.fields?.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 8, rowGap: 4 }}>
            {content.fields.map((field) => (
              <React.Fragment key={field.key}>
                <Text type="secondary" style={{ fontSize: 11, textTransform: "capitalize" }}>
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
