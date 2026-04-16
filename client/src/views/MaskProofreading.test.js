import React from "react";
import { render, screen } from "@testing-library/react";

import MaskProofreading from "./MaskProofreading";

jest.mock("./EHTool", () => (props) => (
  <div
    data-testid="eh-tool"
    data-workflow-id={String(props.workflowId)}
    data-session-id={String(props.savedSessionId)}
  />
));

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: () => ({ workflow: { id: 42 } }),
}));

describe("MaskProofreading", () => {
  it("renders EHTool and passes the active workflow id", () => {
    render(<MaskProofreading />);

    const ehTool = screen.getByTestId("eh-tool");
    expect(ehTool).toBeTruthy();
    expect(ehTool.getAttribute("data-workflow-id")).toBe("42");
  });
});
