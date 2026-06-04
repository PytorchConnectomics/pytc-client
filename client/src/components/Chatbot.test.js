import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import Chatbot from "./Chatbot";
import { WorkflowContext } from "../contexts/WorkflowContext";
import { getWorkflowAgentConversation, queryChatBot } from "../api";

jest.mock("../api", () => ({
  getWorkflowAgentConversation: jest.fn().mockResolvedValue({ messages: [] }),
  queryChatBot: jest.fn(),
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

function renderChatbot(workflowValue = {}, props = {}) {
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

  const renderResult = render(
    <WorkflowContext.Provider value={value}>
      <Chatbot onClose={jest.fn()} {...props} />
    </WorkflowContext.Provider>,
  );
  return { ...value, ...renderResult };
}

describe("Chatbot workflow routing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.sessionStorage.clear();
    getWorkflowAgentConversation.mockResolvedValue({ messages: [] });
    queryChatBot.mockResolvedValue({ response: "generic response" });
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
    expect(await screen.findByText("Do this: run the model.")).toBeTruthy();
  });

  it("routes casual segmentation language to the workflow agent", async () => {
    const workflow = renderChatbot();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "i wanna segment some dattaaaaaaaaaaa" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "i wanna segment some dattaaaaaaaaaaa",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
  });

  it("keeps one continuous workflow chat across drawer remounts", async () => {
    const firstQueryAgent = jest.fn().mockResolvedValue({
      response: "I found the current project state.",
      conversationId: 77,
      source: "workflow_orchestrator",
      actions: [],
      commands: [],
      proposals: [],
    });
    const first = renderChatbot({ queryAgent: firstQueryAgent });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "what are we looking at?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    expect(await screen.findByText("I found the current project state.")).toBeTruthy();
    first.unmount();

    const secondQueryAgent = jest.fn().mockResolvedValue({
      response: "Still on the same thread.",
      conversationId: 77,
      source: "workflow_orchestrator",
      actions: [],
      commands: [],
      proposals: [],
    });
    renderChatbot({ queryAgent: secondQueryAgent });

    expect(await screen.findByText("what are we looking at?")).toBeTruthy();
    expect(await screen.findByText("I found the current project state.")).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "again" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(secondQueryAgent).toHaveBeenCalledWith("again", 77);
    });
  });

  it("routes visualization requests to the workflow agent instead of generic chat", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "Do this: view the current volume pair.",
        conversationId: 46,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "open-visualization",
            label: "View data",
            description: "Open the image and mask in the viewer.",
            client_effects: { navigate_to: "visualization" },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can we visualize a volume pair?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "can we visualize a volume pair?",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(await screen.findByText("Do this: view the current volume pair.")).toBeTruthy();
    expect(screen.getAllByText("View data").length).toBeGreaterThan(0);
  });

  it("routes plain data-viewing requests to the workflow agent action cards", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "Do this: view image with seg.",
        conversationId: 53,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "open-visualization",
            label: "View data",
            description: "Open the selected image and mask in the viewer.",
            client_effects: {
              navigate_to: "visualization",
              set_current_image: "data/image/test_im.h5",
              set_current_label: "data/seg/test_mito.h5",
              set_visualization_scales: [1, 1, 1],
              runtime_action: { kind: "load_visualization" },
            },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can we view some data" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "can we view some data",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(await screen.findByText("Do this: view image with seg.")).toBeTruthy();
    expect(screen.getAllByText("View data").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Run in app" })).toBeTruthy();
  });

  it("shows expandable trace details for workflow-agent context checks", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "I checked the mounted project.",
        conversationId: 56,
        source: "workflow_orchestrator",
        actions: [],
        commands: [],
        proposals: [],
        trace: [
          {
            label: "Checked project files",
            detail: "Scanned prepilot_lucchi_pp; found 2 image/seg sets.",
          },
        ],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "what files are here?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "what files are here?",
        null,
      );
    });
    const traceToggle = await screen.findByRole("button", {
      name: /Operational trace/,
    });
    fireEvent.click(traceToggle);
    expect(
      (await screen.findAllByText("Checked project files")).length,
    ).toBeGreaterThan(0);
    expect(
      await screen.findByText(
        "Scanned prepilot_lucchi_pp; found 2 image/seg sets.",
      ),
    ).toBeTruthy();
  });

  it("routes abbreviated visualization phrasing to the workflow agent", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "Do this: view the mounted data.",
        conversationId: 54,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "open-visualization",
            label: "View data",
            description: "Open the selected image and mask in the viewer.",
            client_effects: {
              navigate_to: "visualization",
              runtime_action: { kind: "load_visualization" },
            },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can we vis some data" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "can we vis some data",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(await screen.findByText("Do this: view the mounted data.")).toBeTruthy();
    expect(screen.getAllByText("View data").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Run in app" })).toBeTruthy();
  });

  it("defaults readable active-workflow chat to the workflow agent", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "Do this: inspect workflow status.",
        conversationId: 55,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "show-status",
            label: "Show status",
            description: "Open workflow status.",
            client_effects: { show_workflow_context: true },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can you help me figure this out" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "can you help me figure this out",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(await screen.findByText("Do this: inspect workflow status.")).toBeTruthy();
    expect(screen.getAllByText("Show status").length).toBeGreaterThan(0);
  });

  it("lets general conceptual questions use the regular chat path", async () => {
    const workflow = renderChatbot();
    queryChatBot.mockResolvedValueOnce({
      response: "Binary cross entropy is a loss for binary labels.",
      conversationId: 91,
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "what is binary cross entropy?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(queryChatBot).toHaveBeenCalledWith(
        "what is binary cross entropy?",
        null,
      );
    });
    expect(workflow.queryAgent).not.toHaveBeenCalled();
    expect(
      await screen.findByText("Binary cross entropy is a loss for binary labels."),
    ).toBeTruthy();
  });

  it("routes casual label viewing language to the workflow agent", async () => {
    const workflow = renderChatbot();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can i look at my labels real quick?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "can i look at my labels real quick?",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
  });

  it("routes visualization scale corrections to the workflow agent", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "Do this: reload the viewer with 1,1,1 nm voxel scales.",
        conversationId: 48,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "reload-visualization-scales",
            label: "Reload viewer",
            description: "Reload with updated scales.",
            client_effects: {
              navigate_to: "visualization",
              set_visualization_scales: [1, 1, 1],
              runtime_action: { kind: "load_visualization" },
            },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "the scales are off; reload with 1-1-1" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "the scales are off; reload with 1-1-1",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(
      await screen.findByText("Do this: reload the viewer with 1,1,1 nm voxel scales."),
    ).toBeTruthy();
    expect((await screen.findAllByText("Reload viewer")).length).toBeGreaterThan(0);
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

  it("runs a queued quick next-step request through the workflow agent", async () => {
    const workflow = renderChatbot(
      {
        queryAgent: jest.fn().mockResolvedValue({
          response: "Do this: add a checkpoint or mask/label.",
          conversationId: 45,
          source: "workflow_orchestrator",
          actions: [
            {
              id: "open-files",
              label: "Choose data",
              description: "Pick data.",
              client_effects: { navigate_to: "files" },
            },
          ],
          commands: [],
          proposals: [],
        }),
      },
      {
        queuedWorkflowQuery: {
          id: 1,
          query: "What should I do next?",
          displayText: "What should I do next?",
          source: "quick_next",
        },
      },
    );

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "What should I do next?",
        null,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(await screen.findByText("What should I do next?")).toBeTruthy();
    expect(
      await screen.findByText("Do this: add a checkpoint or mask/label."),
    ).toBeTruthy();
    expect((await screen.findAllByText("Choose data")).length).toBeGreaterThan(0);
  });

  it("keeps workflow follow-up questions with the orchestrator after a workflow answer", async () => {
    const workflow = renderChatbot({
      queryAgent: jest
        .fn()
        .mockResolvedValueOnce({
          response:
            "Do this: Proofread this data. Watch out: Run inference only after checking the pair.",
          conversationId: 51,
          source: "workflow_orchestrator",
          actions: [],
          commands: [],
          proposals: [],
        })
        .mockResolvedValueOnce({
          response: "Do this: open the current image and mask pair first.",
          conversationId: 51,
          source: "workflow_orchestrator",
          actions: [
            {
              id: "open-visualization",
              label: "Show data",
              description: "Open the current pair.",
              client_effects: { navigate_to: "visualization" },
            },
          ],
          commands: [],
          proposals: [],
        }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "what should I do?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    expect(
      await screen.findByText(
        "Do this: Proofread this data. Watch out: Run inference only after checking the pair.",
      ),
    ).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can we take a look at it first?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenLastCalledWith(
        "can we take a look at it first?",
        51,
      );
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(
      await screen.findByText("Do this: open the current image and mask pair first."),
    ).toBeTruthy();
    expect(screen.getAllByText("Show data").length).toBeGreaterThan(0);
  });

  it("routes short clarification follow-ups to the orchestrator after a workflow answer", async () => {
    const workflow = renderChatbot({
      queryAgent: jest
        .fn()
        .mockResolvedValueOnce({
          response: "Do this: show status before starting another action.",
          conversationId: 52,
          source: "workflow_orchestrator",
          actions: [],
          commands: [],
          proposals: [],
        })
        .mockResolvedValueOnce({
          response: "I mean the workflow evidence and readiness status.",
          conversationId: 52,
          source: "workflow_orchestrator",
          actions: [],
          commands: [],
          proposals: [],
        }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "what should I do?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    expect(
      await screen.findByText("Do this: show status before starting another action."),
    ).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "what?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenLastCalledWith("what?", 52);
    });
    expect(queryChatBot).not.toHaveBeenCalled();
    expect(
      await screen.findByText("I mean the workflow evidence and readiness status."),
    ).toBeTruthy();
  });

  it("routes unrelated ambiguous text through the general assistant", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response:
          "I am not sure which app step that maps to. Current next step: Proofread this data.",
        conversationId: 44,
        source: "workflow_orchestrator",
        actions: [],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "mmajkf,ansdjs" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(queryChatBot).toHaveBeenCalledWith("mmajkf,ansdjs", null);
    });
    expect(workflow.queryAgent).not.toHaveBeenCalled();
    expect(await screen.findByText("generic response")).toBeTruthy();
  });

  it("does not render raw JSON tool calls from the general assistant", async () => {
    renderChatbot({ workflow: null, queryAgent: null });
    queryChatBot.mockResolvedValue({
      response:
        '{"name": "visualize_volume_pair", "parameters": {"query": "volume pair visualization"}}',
      conversationId: 47,
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "can we visualize a volume pair?" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(queryChatBot).toHaveBeenCalledWith(
        "can we visualize a volume pair?",
        null,
      );
    });
    expect(screen.queryByText(/"visualize_volume_pair"/)).toBeNull();
    expect(
      await screen.findByText(/I should not have shown that internal command/),
    ).toBeTruthy();
  });

  it("does not render embedded JSON tool calls from the general assistant", async () => {
    renderChatbot({ workflow: null, queryAgent: null });
    queryChatBot.mockResolvedValue({
      response:
        'Here is the revised function call in JSON format:\n{"name":"search_documentation","parameters":{"query":"train"}}',
      conversationId: 49,
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "how do i tune this" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(queryChatBot).toHaveBeenCalledWith("how do i tune this", null);
    });
    expect(screen.queryByText(/search_documentation/)).toBeNull();
    expect(
      await screen.findByText(/I should not have shown that internal command/),
    ).toBeTruthy();
  });

  it("does not expose saved chat history controls in the workflow assistant", () => {
    renderChatbot();

    expect(screen.queryByLabelText("Show conversations")).toBeNull();
    expect(screen.queryByLabelText("New chat")).toBeNull();
  });

  it("restores the continuous workflow chat from session storage", async () => {
    window.sessionStorage.setItem(
      "pytc.workflowAssistant.continuousChat.v1",
      JSON.stringify({
        activeConvoId: 8,
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
      }),
    );
    renderChatbot();

    expect(await screen.findByText("Do this: proofread this data.")).toBeTruthy();
    expect(screen.getAllByText("Proofread this data").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Run in app" })).toBeTruthy();
  });

  it("reconciles persisted proposal statuses with the latest server conversation", async () => {
    window.sessionStorage.setItem(
      "pytc.workflowAssistant.continuousChat.v1",
      JSON.stringify({
        activeConvoId: 8,
        messages: [
          {
            role: "user",
            content: "train this dataset",
          },
          {
            role: "assistant",
            content: "Review this run.",
            source: "workflow_orchestrator",
            workflow_id: 2,
            proposals: [
              {
                id: 201,
                summary: "Approve training run.",
                approval_status: "pending",
                payload: {
                  action: "start_training_run",
                  params: {
                    config_preset: "/project/config.yaml",
                    image_path: "/project/image",
                    label_path: "/project/label",
                    output_path: "/project/out",
                  },
                },
              },
            ],
          },
        ],
      }),
    );
    const queryResult = {
      response: "I checked the conversation state.",
      conversationId: 8,
      source: "workflow_orchestrator",
      proposals: [
        {
          id: 201,
          summary: "Approve training run.",
          approval_status: "approved",
          payload: {
            action: "start_training_run",
            params: {
              config_preset: "/project/config.yaml",
              image_path: "/project/image",
              label_path: "/project/label",
              output_path: "/project/out",
            },
          },
        },
      ],
      actions: [],
      commands: [],
    };
    getWorkflowAgentConversation.mockResolvedValue({
      conversation_id: 8,
      messages: [
        {
          role: "assistant",
          content: "Review this run.",
          source: "workflow_orchestrator",
          workflow_id: 2,
          proposals: [
            {
              id: 201,
              summary: "Approve training run.",
              approval_status: "approved",
              payload: {
                action: "start_training_run",
                params: {
                  config_preset: "/project/config.yaml",
                  image_path: "/project/image",
                  label_path: "/project/label",
                  output_path: "/project/out",
                },
              },
            },
          ],
        },
      ],
    });
    renderChatbot({
      workflow: { id: 2, stage: "setup" },
      queryAgent: jest.fn().mockResolvedValue(queryResult),
    });

    expect(await screen.findByText("Review this run.")).toBeTruthy();
    await waitFor(() => {
      expect(getWorkflowAgentConversation).toHaveBeenCalledWith(2);
    });
    const approveButton = screen.getByRole("button", { name: "Approve" });
    expect(approveButton.disabled).toBe(true);
  });

  it("displays specialist agent badges for persisted proposal metadata", async () => {
    window.sessionStorage.setItem(
      "pytc.workflowAssistant.continuousChat.v1",
      JSON.stringify({
        activeConvoId: 12,
        messages: [
          {
            role: "assistant",
            content: "Review this action.",
            source: "workflow_orchestrator",
            workflow_id: 44,
            proposals: [
              {
                id: 901,
                summary: "Approve app action.",
                payload: {
                  action: "run_client_effects",
                  params: {
                    item_label: "Run inference",
                  },
                },
                specialist_agent: {
                  agent_label: "Inference Specialist",
                  agent_short_label: "INFER",
                  agent_color: "#123abc",
                  agent_icon_key: "eye",
                  agent_border_style: "dashed",
                },
              },
            ],
          },
        ],
      }),
    );

    renderChatbot({
      workflow: { id: 44, stage: "inference" },
    });

    expect(await screen.findByText("Review this action.")).toBeTruthy();
    expect(screen.getByText("INFER")).toBeTruthy();
  });

  it("proposes approval before running risky non-training app actions", async () => {
    const proposeAgentAction = jest.fn().mockResolvedValue({
      id: 88,
      summary: "Approve app action: Run model.",
      payload: {
        action: "run_client_effects",
        params: { item_label: "Run model" },
      },
    });
    const executeAssistantItem = jest.fn();
    const workflow = renderChatbot({
      proposeAgentAction,
      executeAssistantItem,
      queryAgent: jest.fn().mockResolvedValue({
        response: "Do this: run inference.",
        conversationId: 50,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "run-inference",
            label: "Run model",
            description: "Run inference with the selected inputs.",
            requires_approval: true,
            risk_level: "runs_job",
            client_effects: {
              navigate_to: "inference",
              set_inference_output_path: "/tmp/out",
              runtime_action: { kind: "start_inference" },
            },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "run inference" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith("run inference", null);
    });
    fireEvent.click(await screen.findByRole("button", { name: "Run in app" }));

    await waitFor(() => {
      expect(proposeAgentAction).toHaveBeenCalledWith(
        expect.objectContaining({
          action: "run_client_effects",
          payload: expect.objectContaining({
            item_id: "run-inference",
            item_label: "Run model",
            item_type: "action",
            risk_level: "runs_job",
            runtime_action: { kind: "start_inference" },
            client_effects: expect.objectContaining({
              set_inference_output_path: "/tmp/out",
            }),
          }),
        }),
      );
    });
    expect(executeAssistantItem).not.toHaveBeenCalled();
  });

  it("populates the training review form before creating the approval card", async () => {
    const callOrder = [];
    const runClientEffects = jest.fn().mockImplementation(async () => {
      callOrder.push("form");
    });
    const proposeAgentAction = jest.fn().mockImplementation(async () => {
      callOrder.push("proposal");
      return {
        id: 89,
        summary: "Approve training run.",
        payload: {
          action: "start_training_run",
          params: { item_label: "Train model" },
        },
      };
    });
    const workflow = renderChatbot({
      runClientEffects,
      proposeAgentAction,
      queryAgent: jest.fn().mockResolvedValue({
        response: "I staged a clean training run. Review the run card.",
        conversationId: 51,
        source: "workflow_orchestrator",
        actions: [
          {
            id: "start-training",
            label: "Train model",
            description: "Start training with the approved volume subset.",
            requires_approval: true,
            risk_level: "runs_job",
            run_label: "Review run",
            client_effects: {
              navigate_to: "training",
              set_training_config_preset: "/project/config.yaml",
              set_training_image_path: "/project/subset/image",
              set_training_label_path: "/project/subset/seg",
              set_training_output_path: "/project/output",
              set_training_log_path: "/project/log.txt",
              runtime_action: {
                kind: "start_training",
                autopick_parameters: true,
                parameter_mode: "agent_default",
              },
            },
          },
        ],
        commands: [],
        proposals: [],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "train on the good ground truth" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "train on the good ground truth",
        null,
      );
    });
    fireEvent.click(await screen.findByRole("button", { name: "Review run" }));

    await waitFor(() => {
      expect(proposeAgentAction).toHaveBeenCalled();
    });
    expect(callOrder).toEqual(["form", "proposal"]);
    expect(runClientEffects).toHaveBeenCalledWith({
      navigate_to: "training",
      set_training_config_preset: "/project/config.yaml",
      set_training_image_path: "/project/subset/image",
      set_training_label_path: "/project/subset/seg",
      set_training_output_path: "/project/output",
      set_training_log_path: "/project/log.txt",
    });
    expect(proposeAgentAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "start_training_run",
        payload: expect.objectContaining({
          config_preset: "/project/config.yaml",
          image_path: "/project/subset/image",
          label_path: "/project/subset/seg",
          output_path: "/project/output",
          autopick_parameters: true,
        }),
      }),
    );
  });

  it("shows operational proposal trace sections for approval cards", async () => {
    const workflow = renderChatbot({
      queryAgent: jest.fn().mockResolvedValue({
        response: "I drafted an execution proposal.",
        conversationId: 57,
        source: "workflow_orchestrator",
        actions: [],
        commands: [],
        proposals: [
          {
            id: 77,
            summary: "Approve proposed action.",
            payload: {
              action: "run_client_effects",
              params: {
                item_label: "Run model",
                action_card: {
                  trace: [
                    {
                      label: "Checked inputs",
                      detail: "Model checkpoint and image pair resolved.",
                      status: "checked",
                      category: "checked",
                    },
                  ],
                  requires_approval: true,
                  risk_level: "runs_job",
                  approval_reason: "Model inference is expensive.",
                  input_artifacts: [{ path: "/project/images/input.tif" }],
                  output_artifacts: [{ path: "/project/results/output.tif" }],
                  project_memory_update: { stage: "inference" },
                },
              },
            },
          },
        ],
      }),
    });

    fireEvent.change(screen.getByPlaceholderText("Message"), {
      target: { value: "run inference for review" },
    });
    fireEvent.keyPress(screen.getByPlaceholderText("Message"), {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    await waitFor(() => {
      expect(workflow.queryAgent).toHaveBeenCalledWith(
        "run inference for review",
        null,
      );
    });
    expect(await screen.findByRole("button", { name: "Approve" })).toBeTruthy();

    const traceToggle = await screen.findByRole("button", {
      name: /Operational trace/,
    });
    fireEvent.click(traceToggle);
    expect(await screen.findByText("Inspected facts")).toBeTruthy();
    expect(await screen.findByText(/Checked inputs/)).toBeTruthy();
    expect(await screen.findByText(/Risk level: runs_job/)).toBeTruthy();
    expect(
      await screen.findByText(
        /(Input · path: \/project\/images\/input\.tif)|(Input · artifact: \/project\/images\/input\.tif)/,
      ),
    ).toBeTruthy();
    expect(
      await screen.findByText(
        /(Output · path: \/project\/results\/output\.tif)|(Output · artifact: \/project\/results\/output\.tif)/,
      ),
    ).toBeTruthy();
  });

  it("recreates a missing persisted proposal before approving it", async () => {
    const approveAgentAction = jest
      .fn()
      .mockRejectedValueOnce(new Error("404: Agent proposal not found"))
      .mockResolvedValueOnce({});
    const freshProposal = {
      id: 335,
      summary: "Approve training run.",
      payload: {
        action: "start_training_run",
        params: {
          config_preset: "/project/config.yaml",
          image_path: "/project/subset/image",
          label_path: "/project/subset/seg",
          output_path: "/project/output",
        },
      },
    };
    const proposeAgentAction = jest.fn().mockResolvedValue(freshProposal);
    window.sessionStorage.setItem(
      "pytc.workflowAssistant.continuousChat.v1",
      JSON.stringify({
        activeConvoId: 10,
        messages: [
          {
            role: "assistant",
            content: "Review this run.",
            source: "workflow_orchestrator",
            workflow_id: 112,
            proposals: [
              {
                id: 334,
                summary: "Approve training run.",
                payload: {
                  action: "start_training_run",
                  params: {
                    config_preset: "/project/config.yaml",
                    image_path: "/project/subset/image",
                    label_path: "/project/subset/seg",
                    output_path: "/project/output",
                  },
                },
              },
            ],
          },
        ],
      }),
    );

    renderChatbot({
      workflow: { id: 112, stage: "setup" },
      approveAgentAction,
      proposeAgentAction,
    });

    expect(await screen.findByText("Review this run.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(approveAgentAction).toHaveBeenNthCalledWith(1, 334);
      expect(proposeAgentAction).toHaveBeenCalledWith({
        action: "start_training_run",
        summary: "Approve training run.",
        payload: {
          config_preset: "/project/config.yaml",
          image_path: "/project/subset/image",
          label_path: "/project/subset/seg",
          output_path: "/project/output",
        },
      });
      expect(approveAgentAction).toHaveBeenNthCalledWith(2, 335);
    });
  });

  it("removes stale workflow action cards from the continuous chat", async () => {
    window.sessionStorage.setItem(
      "pytc.workflowAssistant.continuousChat.v1",
      JSON.stringify({
        activeConvoId: 9,
        messages: [
          {
            role: "assistant",
            content: "This message came from another workflow.",
            source: "workflow_orchestrator",
            workflow_id: 999,
            actions: [
              {
                id: "stale-action",
                label: "Stale action",
                description: "Should not be runnable here.",
                client_effects: { navigate_to: "training" },
              },
            ],
            commands: [
              {
                id: "stale-command",
                title: "Stale command",
                description: "Should not be runnable here.",
                command: "app training start",
                client_effects: { navigate_to: "training" },
              },
            ],
            proposals: [
              {
                id: 100,
                summary: "Stale approval.",
                payload: {
                  action: "run_client_effects",
                  params: { item_label: "Stale action" },
                },
              },
            ],
          },
        ],
      }),
    );
    renderChatbot({ workflow: { id: 1, stage: "setup" } });

    expect(
      await screen.findByText("This message came from another workflow."),
    ).toBeTruthy();
    expect(screen.queryByText("Stale action")).toBeNull();
    expect(screen.queryByText("Stale command")).toBeNull();
    expect(screen.queryByRole("button", { name: "Run in app" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Execute" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });

  it("explains when a stale reviewed run card was removed", async () => {
    window.sessionStorage.setItem(
      "pytc.workflowAssistant.continuousChat.v1",
      JSON.stringify({
        activeConvoId: 9,
        messages: [
          {
            role: "assistant",
            content: "I staged that run. Review the run card before launching it.",
            source: "workflow_orchestrator",
            workflow_id: 999,
            actions: [
              {
                id: "start-training",
                label: "Train model",
                run_label: "Review run",
                client_effects: { navigate_to: "training" },
              },
            ],
            commands: [],
            proposals: [],
          },
        ],
      }),
    );
    renderChatbot({ workflow: { id: 1, stage: "setup" } });

    expect(await screen.findByText(/Review the run card/)).toBeTruthy();
    expect(await screen.findByText(/That run card belonged/)).toBeTruthy();
    expect(screen.queryByText("Train model")).toBeNull();
    expect(screen.queryByRole("button", { name: "Review run" })).toBeNull();
  });
});
