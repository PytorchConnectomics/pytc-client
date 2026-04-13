import React, { createContext, useContext, useMemo, useState } from "react";

const ACTOR_ALL = "all";

const WorkflowTimelineContext = createContext(null);

const normalize = (value) => String(value || "").trim().toLowerCase();

export function WorkflowTimelineProvider({ events, children }) {
  const [actorFilter, setActorFilter] = useState(ACTOR_ALL);
  const [eventTypeFilter, setEventTypeFilter] = useState("");

  const normalizedEventTypeFilter = useMemo(
    () => normalize(eventTypeFilter),
    [eventTypeFilter],
  );

  const filteredEvents = useMemo(() => {
    const hasActorFilter = actorFilter !== ACTOR_ALL;
    const hasEventTypeFilter = Boolean(normalizedEventTypeFilter);

    if (!hasActorFilter && !hasEventTypeFilter) {
      return events;
    }

    return events.filter((event) => {
      if (hasActorFilter && event.actor !== actorFilter) {
        return false;
      }

      if (!hasEventTypeFilter) {
        return true;
      }

      return normalize(event.type).includes(normalizedEventTypeFilter);
    });
  }, [actorFilter, events, normalizedEventTypeFilter]);

  const clearFilters = () => {
    setActorFilter(ACTOR_ALL);
    setEventTypeFilter("");
  };

  const value = useMemo(
    () => ({
      actorFilter,
      setActorFilter,
      eventTypeFilter,
      setEventTypeFilter,
      filteredEvents,
      clearFilters,
    }),
    [actorFilter, eventTypeFilter, filteredEvents],
  );

  return (
    <WorkflowTimelineContext.Provider value={value}>
      {children}
    </WorkflowTimelineContext.Provider>
  );
}

export function useWorkflowTimeline() {
  const context = useContext(WorkflowTimelineContext);
  if (!context) {
    throw new Error(
      "useWorkflowTimeline must be used inside WorkflowTimelineProvider",
    );
  }

  return context;
}
