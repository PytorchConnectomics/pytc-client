import React from "react";
import { Button, Empty, List, Space, Tag, Typography } from "antd";
import { CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { useWorkflow } from "../contexts/WorkflowContext";

const { Text } = Typography;

const STAGE_LABELS = {
  setup: "Setup",
  visualization: "Visualization",
  inference: "Inference",
  proofreading: "Proofreading",
  retraining_staged: "Retraining staged",
  evaluation: "Evaluation",
};

function formatEventTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function WorkflowTimeline({ limit = 8 }) {
  const workflowContext = useWorkflow();
  const workflow = workflowContext?.workflow;
  const events = workflowContext?.events || [];
  const approveAgentAction = workflowContext?.approveAgentAction;
  const rejectAgentAction = workflowContext?.rejectAgentAction;

  if (!workflowContext) return null;

  const visibleEvents = events.slice(-limit).reverse();
  const stageLabel = STAGE_LABELS[workflow?.stage] || workflow?.stage || "Loading";

  return (
    <div
      data-testid="workflow-timeline"
      style={{
        borderTop: "1px solid #f0f0f0",
        borderBottom: "1px solid #f0f0f0",
        padding: "10px 16px",
        background: "#fbfbfb",
      }}
    >
      <Space
        size="small"
        style={{ display: "flex", justifyContent: "space-between" }}
      >
        <Space size="small">
          <Text strong style={{ fontSize: 13 }}>
            Workflow
          </Text>
          <Tag color="blue" style={{ margin: 0 }}>
            {stageLabel}
          </Tag>
        </Space>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {workflow?.title || "Segmentation Workflow"}
        </Text>
      </Space>

      {visibleEvents.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="No workflow events yet"
          style={{ margin: "8px 0 0" }}
        />
      ) : (
        <List
          size="small"
          dataSource={visibleEvents}
          style={{ marginTop: 8 }}
          renderItem={(event) => {
            const isPendingProposal =
              event.event_type === "agent.proposal_created" &&
              event.approval_status === "pending";
            return (
              <List.Item
                style={{
                  padding: "6px 0",
                  alignItems: "flex-start",
                  borderBlockEnd: "none",
                }}
                actions={
                  isPendingProposal
                    ? [
                        <Button
                          key="approve"
                          size="small"
                          icon={<CheckOutlined />}
                          onClick={() => approveAgentAction?.(event.id)}
                        >
                          Approve
                        </Button>,
                        <Button
                          key="reject"
                          size="small"
                          icon={<CloseOutlined />}
                          onClick={() => rejectAgentAction?.(event.id)}
                        >
                          Reject
                        </Button>,
                      ]
                    : []
                }
              >
                <List.Item.Meta
                  title={
                    <Space size="small" wrap>
                      <Text style={{ fontSize: 12 }}>{event.summary}</Text>
                      {event.approval_status !== "not_required" && (
                        <Tag style={{ margin: 0 }}>
                          {event.approval_status}
                        </Tag>
                      )}
                    </Space>
                  }
                  description={
                    <Space size="small" wrap>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {event.actor}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {event.event_type}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {formatEventTime(event.created_at)}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </div>
  );
}

export default WorkflowTimeline;
