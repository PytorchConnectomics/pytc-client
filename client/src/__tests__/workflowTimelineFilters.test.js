import {
  DEFAULT_TIMELINE_FILTERS,
  filterTimelineEvents,
} from "../contexts/workflow/timelineFilters";

const EVENTS = [
  { id: "1", actor: "user", event_type: "dataset.loaded" },
  { id: "2", actor: "agent", event_type: "agent.proposal_created" },
  { id: "3", actor: "system", event_type: "inference.completed" },
  { id: "4", actor: "agent", event_type: "agent.proposal_approved" },
];

describe("workflow timeline filters", () => {
  it("preserves the full timeline by default", () => {
    const visible = filterTimelineEvents(EVENTS, DEFAULT_TIMELINE_FILTERS);
    expect(visible).toHaveLength(EVENTS.length);
    expect(visible).toBe(EVENTS);
  });

  it("filters by actor and event type combinations", () => {
    expect(filterTimelineEvents(EVENTS, { actor: "agent", eventType: "" })).toEqual([
      EVENTS[1],
      EVENTS[3],
    ]);

    expect(
      filterTimelineEvents(EVENTS, { actor: "agent", eventType: "approved" }),
    ).toEqual([EVENTS[3]]);

    expect(
      filterTimelineEvents(EVENTS, { actor: "all", eventType: "proposal" }),
    ).toEqual([EVENTS[1], EVENTS[3]]);
  });
});
