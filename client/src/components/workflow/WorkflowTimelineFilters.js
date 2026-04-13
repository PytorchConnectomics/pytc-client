import React from "react";
import { useWorkflowTimeline } from "../../contexts/workflow/WorkflowTimelineContext";

function WorkflowTimelineFilters() {
  const {
    actorFilter,
    setActorFilter,
    eventTypeFilter,
    setEventTypeFilter,
    clearFilters,
  } = useWorkflowTimeline();

  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      <label>
        Actor filter
        <select
          aria-label="Actor filter"
          value={actorFilter}
          onChange={(event) => setActorFilter(event.target.value)}
        >
          <option value="all">All actors</option>
          <option value="user">User</option>
          <option value="agent">Agent</option>
          <option value="system">System</option>
        </select>
      </label>
      <label>
        Event type filter
        <input
          aria-label="Event type filter"
          placeholder="Filter event type"
          value={eventTypeFilter}
          onChange={(event) => setEventTypeFilter(event.target.value)}
        />
      </label>
      <button type="button" onClick={clearFilters}>
        Clear filters
      </button>
    </div>
  );
}

export default WorkflowTimelineFilters;
