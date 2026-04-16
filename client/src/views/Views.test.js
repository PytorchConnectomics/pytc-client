import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import Views from "./Views";

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: () => null,
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
    Button: ({ children, ...props }) => <button {...props}>{children}</button>,
    Drawer: ({ children, open }) => (open ? <div>{children}</div> : null),
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
jest.mock("../components/Chatbot", () => () => <div>Chatbot</div>);

describe("Views", () => {
  it("shows all active modules without the workflow selector", () => {
    render(<Views />);

    expect(screen.getByText("File Management")).toBeTruthy();
    expect(screen.getByText("Visualization")).toBeTruthy();
    expect(screen.getByText("Model Training")).toBeTruthy();
    expect(screen.getByText("Model Inference")).toBeTruthy();
    expect(screen.getByText("Tensorboard")).toBeTruthy();
    expect(screen.getByText("Mask Proofreading")).toBeTruthy();
    expect(screen.queryByText("SynAnno")).toBeNull();
    expect(screen.queryByText("Change Views")).toBeNull();
    expect(screen.queryByText("Launch Selected")).toBeNull();
    expect(screen.getByText("Files Manager Content")).toBeTruthy();
  });

  it("lazy loads additional tab content after selection", () => {
    render(<Views />);

    expect(screen.queryByText("Visualization Content")).toBeNull();

    fireEvent.click(screen.getByText("Visualization"));

    expect(screen.getByText("Visualization Content")).toBeTruthy();
  });
});
