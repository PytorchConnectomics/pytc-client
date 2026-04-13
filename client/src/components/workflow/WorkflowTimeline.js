import React from "react";
import {
  WorkflowTimelineProvider,
  useWorkflowTimeline,
} from "../../contexts/workflow/WorkflowTimelineContext";
import WorkflowTimelineFilters from "./WorkflowTimelineFilters";

function TimelineEventList() {
  const { filteredEvents } = useWorkflowTimeline();

  return (
    <ul aria-label="Workflow timeline" style={{ margin: 0, paddingLeft: 20 }}>
      {filteredEvents.map((event) => (
        <li key={event.id}>
          <strong>{event.type}</strong> · {event.actor} · {event.message}
        </li>
      ))}
    </ul>
  );
}

function WorkflowTimeline({ events }) {
  return (
    <WorkflowTimelineProvider events={events}>
      <div style={{ display: "grid", gap: 12 }}>
        <WorkflowTimelineFilters />
        <TimelineEventList />
      </div>
    </WorkflowTimelineProvider>
  );
}

export default WorkflowTimeline;
