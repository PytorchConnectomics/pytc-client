import React from "react";
import { Button, Input, Space } from "antd";
import { useWorkflowTimelineFilters } from "../../contexts/workflow/WorkflowTimelineFilterContext";

function WorkflowTimelineFilters() {
  const { filters, setActorFilter, setEventTypeFilter, clearFilters } =
    useWorkflowTimelineFilters();

  return (
    <Space wrap size={8} style={{ width: "100%" }}>
      <label htmlFor="workflow-actor-filter">Actor</label>
      <select
        id="workflow-actor-filter"
        aria-label="Actor filter"
        value={filters.actor}
        onChange={(event) => setActorFilter(event.target.value)}
      >
        <option value="all">All actors</option>
        <option value="user">User</option>
        <option value="agent">Agent</option>
        <option value="system">System</option>
      </select>
      <Input
        aria-label="Event type filter"
        placeholder="Filter event type"
        value={filters.eventType}
        onChange={(event) => setEventTypeFilter(event.target.value)}
        allowClear
        style={{ minWidth: 220 }}
      />
      <Button onClick={clearFilters}>Clear filters</Button>
    </Space>
  );
}

export default WorkflowTimelineFilters;
