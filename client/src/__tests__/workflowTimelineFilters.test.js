import React from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WorkflowTimeline from "../components/workflow/WorkflowTimeline";
import { WorkflowTimelineFilterProvider } from "../contexts/workflow/WorkflowTimelineFilterContext";

const EVENTS = [
  { id: "1", actor: "user", type: "load_dataset", message: "Loaded A" },
  { id: "2", actor: "agent", type: "run_inference", message: "Ran model" },
  { id: "3", actor: "system", type: "save_result", message: "Persisted" },
  { id: "4", actor: "user", type: "save_result", message: "Manual save" },
];

function renderTimeline(events = EVENTS) {
  return render(
    <WorkflowTimelineFilterProvider>
      <WorkflowTimeline events={events} />
    </WorkflowTimelineFilterProvider>,
  );
}

function expectVisibleTypes(types) {
  const items = screen.getAllByRole("listitem");
  expect(items).toHaveLength(types.length);
  types.forEach((type, index) => {
    expect(within(items[index]).getByText(type)).toBeTruthy();
  });
}

describe("workflow timeline filters", () => {
  test("shows full timeline by default", () => {
    renderTimeline();
    expectVisibleTypes([
      "load_dataset",
      "run_inference",
      "save_result",
      "save_result",
    ]);
  });

  test("applies actor and event type filters together", async () => {
    const user = userEvent.setup();
    renderTimeline();

    await user.selectOptions(screen.getByLabelText("Actor filter"), "user");

    const eventTypeInput = screen.getByLabelText("Event type filter");
    await user.type(eventTypeInput, "save");

    expectVisibleTypes(["save_result"]);
    expect(screen.getByText("Manual save")).toBeTruthy();
  });

  test("clear resets filters", async () => {
    const user = userEvent.setup();
    renderTimeline();

    await user.selectOptions(screen.getByLabelText("Actor filter"), "system");
    await user.type(screen.getByLabelText("Event type filter"), "save");

    expectVisibleTypes(["save_result"]);
    expect(screen.getByText("Persisted")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    expectVisibleTypes([
      "load_dataset",
      "run_inference",
      "save_result",
      "save_result",
    ]);
  });
});
