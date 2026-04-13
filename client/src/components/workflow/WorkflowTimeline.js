import React, { useMemo } from "react";
import WorkflowTimelineFilters from "./WorkflowTimelineFilters";
import {
  DEFAULT_TIMELINE_FILTERS,
  filterTimelineEvents,
} from "../../contexts/workflow/timelineFilters";

function WorkflowTimeline({
  events = [],
  filters = DEFAULT_TIMELINE_FILTERS,
  onFilterChange,
  onFilterReset,
}) {
  const visibleEvents = useMemo(
    () => filterTimelineEvents(events, filters),
    [events, filters],
  );

  return (
    <section>
      <WorkflowTimelineFilters
        filters={filters}
        onChange={onFilterChange}
        onReset={onFilterReset}
      />
      <ul aria-label="Workflow timeline">
        {visibleEvents.map((event) => (
          <li key={event.id || `${event.actor}-${event.eventType}-${event.timestamp}`}>
            <strong>{event.actor || "unknown"}</strong>: {event.eventType || event.type}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default WorkflowTimeline;
