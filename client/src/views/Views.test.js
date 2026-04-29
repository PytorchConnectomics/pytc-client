import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import Views from "./Views";

let mockWorkflowContext;

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: () => mockWorkflowContext,
}));

jest.mock("../logging/appEventLog", () => ({
  logClientEvent: jest.fn(),
}));

jest.mock("antd", () => {
  const React = require("react");

  const Layout = ({ children }) => <div>{children}</div>;
  Layout.Content = ({ children }) => <div>{children}</div>;

  const Menu = ({ items = [], onClick }) => (
    <nav>
      {items.map((item) => (
        <button
          key={item.key}
          onClick={() => onClick?.({ key: item.key })}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </nav>
  );

  return {
    Layout,
    Menu,
    Button: ({ children, icon: _icon, ...props }) => (
      <button {...props}>{children}</button>
    ),
    Drawer: ({ children, open }) => (open ? <div>{children}</div> : null),
    message: {
      error: jest.fn(),
      success: jest.fn(),
      warning: jest.fn(),
    },
  };
});

jest.mock("@ant-design/icons", () => {
  const Icon = () => <span />;
  return {
    FolderOpenOutlined: Icon,
    EyeOutlined: Icon,
    ExperimentOutlined: Icon,
    ThunderboltOutlined: Icon,
    DashboardOutlined: Icon,
    BugOutlined: Icon,
  MessageOutlined: Icon,
  };
});

jest.mock("./FilesManager", () => () => <div>Files Manager Content</div>);
jest.mock("./Visualization", () => () => <div>Visualization Content</div>);
jest.mock("./ModelTraining", () => () => <div>Training Content</div>);
jest.mock("./ModelInference", () => () => <div>Inference Content</div>);
jest.mock("./Monitoring", () => () => <div>Monitoring Content</div>);
jest.mock("./MaskProofreading", () => () => (
  <div>Mask Proofreading Content</div>
));
jest.mock("../components/Chatbot", () => (props) => (
  <div>
    <div>Chatbot</div>
    {props.queuedWorkflowQuery?.displayText && (
      <div>{props.queuedWorkflowQuery.displayText}</div>
    )}
  </div>
));

describe("Views", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWorkflowContext = {
      workflow: {
        id: 1,
        stage: "setup",
        metadata: {},
      },
      loading: false,
      startNewWorkflow: jest.fn().mockResolvedValue({}),
      consumeClientEffects: jest.fn(),
    };
  });

  it("shows all active modules without a startup splash screen", () => {
    render(<Views />);

    expect(screen.getByText("Files")).toBeTruthy();
    expect(screen.getByText("Visualize")).toBeTruthy();
    expect(screen.getByText("Train Model")).toBeTruthy();
    expect(screen.getByText("Run Model")).toBeTruthy();
    expect(screen.getByText("Monitor")).toBeTruthy();
    expect(screen.getByText("Proofread")).toBeTruthy();
    expect(screen.queryByText("What are you trying to do?")).toBeNull();
    expect(screen.queryByText("Confirm project folders")).toBeNull();
    expect(screen.getByText("Files Manager Content")).toBeTruthy();
  });

  it("lazy loads additional tab content after selection", () => {
    render(<Views />);

    expect(screen.queryByText("Visualization Content")).toBeNull();

    fireEvent.click(screen.getByText("Visualize"));

    expect(screen.getByText("Visualization Content")).toBeTruthy();
  });

  it("starts a fresh workflow from the app shell", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<Views />);
    fireEvent.click(screen.getByText("New project"));

    await waitFor(() => {
      expect(mockWorkflowContext.startNewWorkflow).toHaveBeenCalledWith({
        metadata: { created_from: "new_project_button" },
      });
    });
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("opens the assistant with a quick next-step request", async () => {
    render(<Views />);

    fireEvent.click(screen.getByText("What next?"));

    expect(screen.getByText("Chatbot")).toBeTruthy();
    expect(screen.getByText("What should I do next?")).toBeTruthy();
  });
});
