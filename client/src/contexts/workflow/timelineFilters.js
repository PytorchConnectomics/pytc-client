export const TIMELINE_ACTOR_OPTIONS = ["all", "user", "agent", "system"];

export const DEFAULT_TIMELINE_FILTERS = {
  actor: "all",
  eventType: "",
};

export function normalizeTimelineFilters(filters = {}) {
  const actor = TIMELINE_ACTOR_OPTIONS.includes(filters.actor)
    ? filters.actor
    : DEFAULT_TIMELINE_FILTERS.actor;
  const eventType = (filters.eventType || "").trim();

  return {
    actor,
    eventType,
  };
}

export function eventMatchesTimelineFilters(event, filters = DEFAULT_TIMELINE_FILTERS) {
  const normalized = normalizeTimelineFilters(filters);
  const actor = (event?.actor || "").toLowerCase();
  const eventType = (event?.eventType || event?.type || "").toLowerCase();

  if (normalized.actor !== "all" && actor !== normalized.actor) {
    return false;
  }

  if (!normalized.eventType) {
    return true;
  }

  return eventType.includes(normalized.eventType.toLowerCase());
}

export function filterTimelineEvents(events = [], filters = DEFAULT_TIMELINE_FILTERS) {
  if (!Array.isArray(events) || events.length === 0) {
    return [];
  }

  const normalized = normalizeTimelineFilters(filters);

  if (normalized.actor === "all" && !normalized.eventType) {
    return events;
  }

  return events.filter((event) => eventMatchesTimelineFilters(event, normalized));
}
