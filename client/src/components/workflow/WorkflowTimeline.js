import React, { useMemo } from "react";
import { Typography } from "antd";
import WorkflowTimelineFilters from "./WorkflowTimelineFilters";
import { useWorkflowTimelineFilters } from "../../contexts/workflow/WorkflowTimelineFilterContext";

const { Text } = Typography;

function WorkflowTimeline({ events = [] }) {
  const { filters } = useWorkflowTimelineFilters();

  const visibleEvents = useMemo(() => {
    const normalizedType = filters.eventType.trim().toLowerCase();

    return events.filter((event) => {
      const actorMatches =
        filters.actor === "all" || event.actor === filters.actor;
      if (!actorMatches) return false;
      if (!normalizedType) return true;
      return (event.type || "").toLowerCase().includes(normalizedType);
    });
  }, [events, filters.actor, filters.eventType]);

  return (
    <div>
      <WorkflowTimelineFilters />
      {visibleEvents.length === 0 ? (
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">No timeline events</Text>
        </div>
      ) : (
        <ul style={{ marginTop: 12, paddingLeft: 20 }}>
          {visibleEvents.map((event) => (
            <li key={event.id}>
              <Text code>{event.actor}</Text>
              <Text style={{ marginLeft: 8 }}>{event.type}</Text>
              <Text type="secondary" style={{ marginLeft: 8 }}>
                {event.message}
              </Text>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default WorkflowTimeline;
