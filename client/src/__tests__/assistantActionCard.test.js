import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import AssistantActionCard from "../components/chat/AssistantActionCard";

jest.mock("antd", () => ({
  Button: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
  Space: ({ children }) => <div>{children}</div>,
  Tag: ({ children }) => <span>{children}</span>,
  Typography: {
    Text: ({ children }) => <span>{children}</span>,
  },
}));

describe("AssistantActionCard", () => {
  it("renders the action metadata and triggers execution", () => {
    const onRun = jest.fn();
    const action = {
      id: "open-training",
      label: "Open Training",
      description: "Jump to training with staged labels.",
      variant: "primary",
      client_effects: {
        navigate_to: "training",
      },
    };

    render(<AssistantActionCard action={action} onRun={onRun} />);

    expect(screen.getByText("Open Training")).toBeTruthy();
    expect(screen.getByText("Jump to training with staged labels.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Run in app" }));
    expect(onRun).toHaveBeenCalledWith(action);
  });
});
