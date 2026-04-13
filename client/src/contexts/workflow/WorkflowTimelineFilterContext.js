import React, { createContext, useContext, useMemo, useState } from "react";

const DEFAULT_FILTERS = {
  actor: "all",
  eventType: "",
};

const WorkflowTimelineFilterContext = createContext({
  filters: DEFAULT_FILTERS,
  setActorFilter: () => {},
  setEventTypeFilter: () => {},
  clearFilters: () => {},
});

export function WorkflowTimelineFilterProvider({ children }) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const value = useMemo(
    () => ({
      filters,
      setActorFilter: (actor) => {
        setFilters((current) => ({ ...current, actor }));
      },
      setEventTypeFilter: (eventType) => {
        setFilters((current) => ({ ...current, eventType }));
      },
      clearFilters: () => {
        setFilters(DEFAULT_FILTERS);
      },
    }),
    [filters],
  );

  return (
    <WorkflowTimelineFilterContext.Provider value={value}>
      {children}
    </WorkflowTimelineFilterContext.Provider>
  );
}

export function useWorkflowTimelineFilters() {
  return useContext(WorkflowTimelineFilterContext);
}

export { DEFAULT_FILTERS };
