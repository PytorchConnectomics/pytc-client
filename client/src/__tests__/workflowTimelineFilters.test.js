import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import WorkflowTimeline from "../components/workflow/WorkflowTimeline";
import {
  DEFAULT_TIMELINE_FILTERS,
  filterTimelineEvents,
} from "../contexts/workflow/timelineFilters";

const EVENTS = [
  { id: "1", actor: "user", eventType: "message_sent", timestamp: "1" },
  { id: "2", actor: "agent", eventType: "tool_call", timestamp: "2" },
  { id: "3", actor: "system", eventType: "checkpoint_saved", timestamp: "3" },
  { id: "4", actor: "agent", eventType: "message_sent", timestamp: "4" },
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
      filterTimelineEvents(EVENTS, { actor: "agent", eventType: "tool" }),
    ).toEqual([EVENTS[1]]);

    expect(
      filterTimelineEvents(EVENTS, { actor: "all", eventType: "message" }),
    ).toEqual([EVENTS[0], EVENTS[3]]);
  });

  it("updates visible events and supports clear", () => {
    function Harness() {
      const [filters, setFilters] = React.useState(DEFAULT_TIMELINE_FILTERS);
      return (
        <WorkflowTimeline
          events={EVENTS}
          filters={filters}
          onFilterChange={setFilters}
          onFilterReset={() => setFilters(DEFAULT_TIMELINE_FILTERS)}
        />
      );
    }

    render(<Harness />);

    expect(screen.getAllByRole("listitem")).toHaveLength(4);

    fireEvent.change(screen.getByLabelText("Actor filter"), {
      target: { value: "agent" },
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(2);

    fireEvent.change(screen.getByLabelText("Event type filter"), {
      target: { value: "tool" },
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByLabelText("Actor filter").value).toBe("all");
    expect(screen.getByLabelText("Event type filter").value).toBe("");
  });
});
