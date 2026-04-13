import React from "react";
import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WorkflowTimeline from "../components/workflow/WorkflowTimeline";

const events = [
  { id: "1", actor: "user", type: "prompt.submitted", message: "Ask" },
  { id: "2", actor: "agent", type: "tool.called", message: "Search" },
  { id: "3", actor: "system", type: "workflow.started", message: "Init" },
  { id: "4", actor: "agent", type: "tool.result", message: "Done" },
];

const getTimelineText = () => screen.getByLabelText("Workflow timeline").textContent;

const expectVisibleEvents = (visibleMessages) => {
  const text = getTimelineText();
  events.forEach((event) => {
    if (visibleMessages.includes(event.message)) {
      expect(text).toContain(event.message);
    } else {
      expect(text).not.toContain(event.message);
    }
  });
};

describe("workflow timeline filters", () => {
  it("shows full timeline by default", () => {
    render(<WorkflowTimeline events={events} />);

    expectVisibleEvents(["Ask", "Search", "Init", "Done"]);
  });

  it("filters by actor and event type, then can clear filters", async () => {
    const user = userEvent.setup();
    render(<WorkflowTimeline events={events} />);

    await user.selectOptions(screen.getByLabelText("Actor filter"), "agent");
    expectVisibleEvents(["Search", "Done"]);

    await user.type(screen.getByLabelText("Event type filter"), "result");
    expectVisibleEvents(["Done"]);

    await user.click(screen.getByRole("button", { name: /clear filters/i }));
    expectVisibleEvents(["Ask", "Search", "Init", "Done"]);
  });

  it("supports event type filter independently of actor", async () => {
    const user = userEvent.setup();
    render(<WorkflowTimeline events={events} />);

    await user.type(screen.getByLabelText("Event type filter"), "tool");

    expectVisibleEvents(["Search", "Done"]);
  });
});
