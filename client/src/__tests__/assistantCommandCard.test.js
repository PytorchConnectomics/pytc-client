import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import AssistantCommandCard from "../components/chat/AssistantCommandCard";

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

describe("AssistantCommandCard", () => {
  it("renders a terminal-style command block and runs it", () => {
    const onRun = jest.fn();
    const command = {
      id: "prime-training",
      title: "Prime the training screen",
      description: "Move the UI into training setup mode.",
      command: 'app open training\napp training labels set "/tmp/corrected.tif"',
      run_label: "Execute",
      client_effects: {
        navigate_to: "training",
        set_training_label_path: "/tmp/corrected.tif",
      },
    };

    render(<AssistantCommandCard command={command} onRun={onRun} />);

    expect(screen.getByText("Prime the training screen")).toBeTruthy();
    expect(screen.queryByText(/app open training/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Route" }));
    expect(screen.getByText(/app open training/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Execute" }));
    expect(onRun).toHaveBeenCalledWith(command);
  });
});
