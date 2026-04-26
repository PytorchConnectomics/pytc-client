import React, { useMemo, useState } from "react";
import { Button, Empty, Input, List, Select, Space, Tag, Typography } from "antd";
import { useWorkflow } from "../contexts/WorkflowContext";
import AgentProposalCard from "./chat/AgentProposalCard";
import StageHeader from "./workflow/StageHeader";
import {
  DEFAULT_TIMELINE_FILTERS,
  filterTimelineEvents,
  normalizeTimelineFilters,
  TIMELINE_ACTOR_OPTIONS,
} from "../contexts/workflow/timelineFilters";
import {
  getApprovalMeta,
  getSeverityMeta,
} from "../design/workflowDesignSystem";

const { Text } = Typography;

function formatEventTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function WorkflowTimeline({ limit = 8, showFilters = true }) {
  const workflowContext = useWorkflow();
  const workflow = workflowContext?.workflow;
  const events = workflowContext?.events;
  const hotspots = workflowContext?.hotspots || [];
  const impactPreview = workflowContext?.impactPreview;
  const refreshInsights = workflowContext?.refreshInsights;
  const approveAgentAction = workflowContext?.approveAgentAction;
  const rejectAgentAction = workflowContext?.rejectAgentAction;
  const [filters, setFilters] = useState(DEFAULT_TIMELINE_FILTERS);

  const reversedEvents = useMemo(() => [...(events || [])].reverse(), [events]);
  const visibleEvents = useMemo(() => {
    return filterTimelineEvents(reversedEvents, filters).slice(0, limit);
  }, [reversedEvents, filters, limit]);
  const topHotspot = hotspots[0] || null;

  if (!workflowContext) return null;

  return (
    <div
      data-testid="workflow-timeline"
      style={{
        borderTop: "1px solid var(--seg-border-subtle)",
        borderBottom: "1px solid var(--seg-border-subtle)",
        padding: "10px 16px",
        background: "var(--seg-bg-canvas)",
      }}
    >
      <StageHeader
        stage={workflow?.stage}
        title={workflow?.title || "Segmentation Workflow"}
        actionLabel="Refresh Insights"
        onAction={() => refreshInsights?.()}
      />

      {(topHotspot || impactPreview) && (
        <div className="workflow-insight-card">
          {topHotspot && (
            <Space size="small" wrap>
              <Text style={{ fontSize: 12 }} strong>
                Hotspot
              </Text>
              <Tag
                color={getSeverityMeta(topHotspot.severity).color}
                style={{ margin: 0 }}
              >
                {getSeverityMeta(topHotspot.severity).label}
              </Tag>
              <Text style={{ fontSize: 12 }}>{topHotspot.summary}</Text>
            </Space>
          )}
          {impactPreview && (
            <div style={{ marginTop: topHotspot ? 4 : 0 }}>
              <Text style={{ fontSize: 12 }} strong>
                Impact
              </Text>
              <Text style={{ fontSize: 12 }}>
                {` ${impactPreview.summary} (confidence: ${impactPreview.confidence})`}
              </Text>
            </div>
          )}
        </div>
      )}

      {showFilters && (
        <Space size="small" style={{ marginTop: 8, display: "flex" }} wrap>
          <Select
            aria-label="Actor filter"
            size="small"
            value={filters.actor}
            style={{ minWidth: 124 }}
            options={TIMELINE_ACTOR_OPTIONS.map((value) => ({
              value,
              label: value === "all" ? "All actors" : value,
            }))}
            onChange={(value) =>
              setFilters((prev) =>
                normalizeTimelineFilters({ ...prev, actor: value }),
              )
            }
          />
          <Input
            aria-label="Event type filter"
            size="small"
            value={filters.eventType}
            placeholder="Filter event type"
            style={{ maxWidth: 180 }}
            onChange={(event) =>
              setFilters((prev) =>
                normalizeTimelineFilters({
                  ...prev,
                  eventType: event.target.value,
                }),
              )
            }
          />
          <Button
            size="small"
            onClick={() => setFilters(DEFAULT_TIMELINE_FILTERS)}
          >
            Clear
          </Button>
        </Space>
      )}

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
                        <Tag key="pending" color="gold">
                          Needs review
                        </Tag>,
                      ]
                    : []
                }
              >
                <List.Item.Meta
                  title={
                    <Space size="small" wrap>
                      <Text style={{ fontSize: 12 }}>{event.summary}</Text>
                      {event.approval_status !== "not_required" && (
                        <Tag
                          color={getApprovalMeta(event.approval_status).color}
                          style={{ margin: 0 }}
                        >
                          {getApprovalMeta(event.approval_status).label}
                        </Tag>
                      )}
                    </Space>
                  }
                  description={
                    <div>
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
                      {isPendingProposal && (
                        <AgentProposalCard
                          proposal={{
                            ...(event.payload || {}),
                            type: event.payload?.action || "agent_proposal",
                            rationale: event.summary,
                            ...(event.payload?.params || {}),
                          }}
                          onApprove={() => approveAgentAction?.(event.id)}
                          onReject={() => rejectAgentAction?.(event.id)}
                        />
                      )}
                    </div>
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
