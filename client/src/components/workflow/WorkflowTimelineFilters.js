import React from "react";
import {
  DEFAULT_TIMELINE_FILTERS,
  TIMELINE_ACTOR_OPTIONS,
} from "../../contexts/workflow/timelineFilters";

const actorLabels = {
  all: "All actors",
  user: "User",
  agent: "Agent",
  system: "System",
};

function WorkflowTimelineFilters({
  filters = DEFAULT_TIMELINE_FILTERS,
  onChange,
  onReset,
}) {
  const actorValue = filters.actor || DEFAULT_TIMELINE_FILTERS.actor;
  const eventTypeValue = filters.eventType || DEFAULT_TIMELINE_FILTERS.eventType;

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <label>
        Actor
        <select
          aria-label="Actor filter"
          value={actorValue}
          onChange={(event) => onChange?.({ ...filters, actor: event.target.value })}
        >
          {TIMELINE_ACTOR_OPTIONS.map((actor) => (
            <option key={actor} value={actor}>
              {actorLabels[actor]}
            </option>
          ))}
        </select>
      </label>

      <label>
        Event type
        <input
          aria-label="Event type filter"
          type="text"
          value={eventTypeValue}
          placeholder="Filter event type"
          onChange={(event) =>
            onChange?.({ ...filters, eventType: event.target.value })
          }
        />
      </label>

      <button type="button" onClick={() => onReset?.()}>
        Clear
      </button>
    </div>
  );
}

export default WorkflowTimelineFilters;
