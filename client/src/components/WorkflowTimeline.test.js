import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import WorkflowTimeline from "./WorkflowTimeline";
import { WorkflowContext } from "../contexts/WorkflowContext";

jest.mock("antd", () => {
  const React = require("react");
  const List = ({ dataSource = [], renderItem }) => (
    <div>
      {dataSource.map((item, index) => (
        <React.Fragment key={item.id || index}>
          {renderItem(item, index)}
        </React.Fragment>
      ))}
    </div>
  );
  List.Item = ({ children, actions = [] }) => (
    <div>
      {children}
      {actions.map((action, index) => (
        <span key={index}>{action}</span>
      ))}
    </div>
  );
  List.Item.Meta = ({ title, description }) => (
    <div>
      <div>{title}</div>
      <div>{description}</div>
    </div>
  );

  const Empty = ({ description }) => <div>{description}</div>;
  Empty.PRESENTED_IMAGE_SIMPLE = "simple";

  return {
    Button: ({ children, icon, ...props }) => (
      <button type="button" {...props}>
        {icon}
        {children}
      </button>
    ),
    Empty,
    List,
    Space: ({ children }) => <span>{children}</span>,
    Tag: ({ children }) => <span>{children}</span>,
    Typography: {
      Text: ({ children }) => <span>{children}</span>,
    },
  };
});

jest.mock("@ant-design/icons", () => {
  const Icon = () => <span />;
  return {
    CheckOutlined: Icon,
    CloseOutlined: Icon,
  };
});

jest.mock("../contexts/WorkflowContext", () => {
  const React = require("react");
  const WorkflowContext = React.createContext(null);
  return {
    WorkflowContext,
    useWorkflow: () => React.useContext(WorkflowContext),
  };
});

const workflow = {
  id: 1,
  title: "Test Workflow",
  stage: "proofreading",
};

function renderTimeline(overrides = {}) {
  const value = {
    workflow,
    events: [],
    approveAgentAction: jest.fn(),
    rejectAgentAction: jest.fn(),
    ...overrides,
  };
  render(
    <WorkflowContext.Provider value={value}>
      <WorkflowTimeline />
    </WorkflowContext.Provider>,
  );
  return value;
}

describe("WorkflowTimeline", () => {
  it("renders workflow stage and chronological evidence", () => {
    renderTimeline({
      events: [
        {
          id: 1,
          actor: "user",
          event_type: "dataset.loaded",
          stage: "proofreading",
          summary: "Loaded dataset.",
          approval_status: "not_required",
          created_at: "2026-04-12T12:00:00Z",
        },
      ],
    });

    expect(screen.getByText("Proofreading")).toBeTruthy();
    expect(screen.getByText("Loaded dataset.")).toBeTruthy();
    expect(screen.getByText("dataset.loaded")).toBeTruthy();
  });

  it("exposes approve and reject controls for pending agent proposals", () => {
    const approveAgentAction = jest.fn();
    const rejectAgentAction = jest.fn();
    renderTimeline({
      approveAgentAction,
      rejectAgentAction,
      events: [
        {
          id: 7,
          actor: "agent",
          event_type: "agent.proposal_created",
          stage: "proofreading",
          summary: "Stage corrected masks.",
          approval_status: "pending",
          created_at: "2026-04-12T12:00:00Z",
        },
      ],
    });

    fireEvent.click(screen.getByText("Approve"));
    fireEvent.click(screen.getByText("Reject"));

    expect(approveAgentAction).toHaveBeenCalledWith(7);
    expect(rejectAgentAction).toHaveBeenCalledWith(7);
  });
});
