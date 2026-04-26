import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import Chatbot from "./Chatbot";
import { WorkflowContext } from "../contexts/WorkflowContext";
import {
  clearChat,
  deleteConversation,
  getConversation,
  listConversations,
  queryChatBot,
  updateConversationTitle,
} from "../api";

jest.mock("../api", () => ({
  clearChat: jest.fn(),
  deleteConversation: jest.fn(),
  getConversation: jest.fn(),
  listConversations: jest.fn(),
  queryChatBot: jest.fn(),
  updateConversationTitle: jest.fn(),
}));

jest.mock("../logging/appEventLog", () => ({
  logClientEvent: jest.fn(),
}));

jest.mock("react-markdown", () => {
  const React = require("react");
  return function ReactMarkdown({ children }) {
    return React.createElement("div", null, children);
  };
});

jest.mock("remark-gfm", () => () => {});

function renderChatbot(workflowValue = {}) {
  window.matchMedia = jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  }));
  window.HTMLElement.prototype.scrollIntoView = jest.fn();

  const value = {
    workflow: { id: 1, stage: "inference" },
    queryAgent: jest.fn().mockResolvedValue({
      response: "Do this: run the model.",
      conversationId: 42,
      source: "workflow_orchestrator",
      actions: [],
      commands: [],
      proposals: [],
    }),
    ...workflowValue,
  };

  render(
    <WorkflowContext.Provider value={value}>
      <Chatbot onClose={jest.fn()} />
    </WorkflowContext.Provider>,
  );
  return value;
}

describe("Chatbot workflow routing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    listConversations.mockResolvedValue([]);
    clearChat.mockResolvedValue({});
    deleteConversation.mockResolvedValue({});
    getConversation.mockResolvedValue({ id: 1, messages: [] });
    queryChatBot.mockResolvedValue({ response: "generic response" });
    updateConversationTitle.mockImplementation((id, title) =>
      Promise.resolve({ id, title }),
    );
  });

  it("routes segmentation requests to the workflow agent instead of generic chat", async () => {
    const workflow = renderChatbot();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "I want to get my volume segmented" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "I want to get my volume segmented",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    await waitFor(() => expect(listConversations).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Do this: run the model.")).toBeTruthy();
  });

  it("routes greetings to the workflow agent so internal LLM prompts cannot leak", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "Hi. I can help with this segmentation loop.",
        conversationId: 43,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "start-proofreading",
            label: "Proofread this data",
            description: "Open proofreading.",
            client_effects: {},
          },
        ],
        commands: [
          {
            id: "start-proofreading-command",
            title: "Proofread this data",
            description: "Open proofreading.",
            command: "app proofreading start",
            client_effects: {},
          },
        ],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "hi!" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith("hi!", null);
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(
      await screen.findByText("Hi. I can help with this segmentation loop."),
    ).toBeTruthy();
    expect(screen.queryByText("Proofread this data")).toBeNull();
  });

  it("keeps workflow slash commands in chat history while routing them to the orchestrator", async () => {
    const workflow = renderChatbot();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "/infer" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith("run model", null);
    });
    expect(queryChatBot).not.toHaveBeenCalled();
  });

  it("can rename saved chats from the conversation list", async () => {
    listConversations.mockResolvedValue([{ id: 7, title: "Old project chat" }]);
    renderChatbot();

    fireEvent.click(screen.getByLabelText("Show conversations"));
    expect(await screen.findByText("Old project chat")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Rename chat Old project chat"));
    fireEvent.change(screen.getByLabelText("Rename chat Old project chat"), {
      target: { value: "Mito proofreading run" },
    });
    fireEvent.keyDown(screen.getByLabelText("Rename chat Old project chat"), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(updateConversationTitle).toHaveBeenCalledWith(
        7,
        "Mito proofreading run",
      );
    });
  });

  it("renders persisted assistant action cards when loading chat history", async () => {
    listConversations.mockResolvedValue([{ id: 8, title: "Action history" }]);
    getConversation.mockResolvedValue({
      id: 8,
      title: "Action history",
      messages: [
        { role: "user", content: "proofread this" },
        {
          role: "assistant",
          content: "Do this: proofread this data.",
          source: "workflow_orchestrator",
          actions: [
            {
              id: "start-proofreading",
              label: "Proofread this data",
              description: "Open proofreading.",
              client_effects: {},
            },
          ],
          commands: [],
          proposals: [],
        },
      ],
    });
    renderChatbot();

    fireEvent.click(screen.getByLabelText("Show conversations"));
    fireEvent.click(await screen.findByText("Action history"));

    expect(await screen.findByText("Do this: proofread this data.")).toBeTruthy();
    expect(await screen.findByText("Proofread this data")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Run in app" })).toBeTruthy();
  });
});
