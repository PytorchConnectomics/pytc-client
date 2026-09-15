import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgentTeamPanel from "./AgentTeamPanel";
import { apiClient } from "../../api";

jest.mock("../../api", () => ({ apiClient: { get: jest.fn(), post: jest.fn() } }));
const run = {
  id: "r1", workflow_id: 1, status: "completed", stale: false,
  actions: [{ label: "Open proofreading", query: "Start proofreading" }],
  created_at: "2026-09-15T12:00:00Z", summary: "Start with proofreading.",
  tasks: [{ id: "t1", role: "data", name: "Data specialist", status: "completed", tools: ["inspect_tiff"],
    goal: "Inspect this pair", context: { workflow_id: 1 },
    result: { observations: ["Labels: 23 nonzero IDs."], facts: {}, blockers: [], actions: [{ label: "Open proofreading", query: "Start proofreading" }] } }],
};
beforeEach(() => {
  jest.clearAllMocks();
  window.matchMedia = jest.fn().mockImplementation(() => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() }));
});
test("loads persisted delegation and hands its action to the existing chat", async () => {
  apiClient.get.mockResolvedValue({ data: [run] });
  apiClient.post.mockResolvedValue({ data: { id: "view", workflow_id: 1, client_effects: { runtime_action: { kind: "start_proofreading" } } } });
  const action = jest.fn();
  render(<AgentTeamPanel workflowId={1} onAction={action} />);
  expect(await screen.findByText("Labels: 23 nonzero IDs.")).toBeTruthy();
  fireEvent.click(screen.getByText("Open proofreading"));
  await waitFor(() => expect(action).toHaveBeenCalledWith(expect.objectContaining({ id: "view", workflow_id: 1 })));
  expect(apiClient.post).toHaveBeenCalledWith("/api/workflows/1/team-runs/r1/actions/0");
  expect(screen.getByText(/model reasoning (is not enabled|was not used)/)).toBeTruthy();
});
test("stale results cannot launch an app action", async () => {
  apiClient.get.mockResolvedValue({ data: [{ ...run, stale: true }] });
  render(<AgentTeamPanel workflowId={1} onAction={jest.fn()} />);
  expect((await screen.findByText("Open proofreading")).closest("button").disabled).toBe(true);
  expect(screen.getByText(/Project inputs changed/)).toBeTruthy();
});
test("starts a scoped check and shows a request failure", async () => {
  apiClient.get.mockResolvedValue({ data: [] });
  apiClient.post.mockRejectedValue({ response: { data: { detail: "Worker unavailable" } } });
  render(<AgentTeamPanel workflowId={2} />);
  await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
  fireEvent.click(screen.getByText("Check project"));
  expect(await screen.findByText("Worker unavailable")).toBeTruthy();
  expect(apiClient.post).toHaveBeenCalledWith('/api/workflows/2/team-runs', expect.objectContaining({ scope: 'project', request_key: expect.any(String) }));
});
test("discards a response from the previous project", async () => {
  let finishOld;
  apiClient.get.mockImplementation((url) => url.includes('/1/') ? new Promise((resolve) => { finishOld = resolve; }) : Promise.resolve({ data: [] }));
  const view = render(<AgentTeamPanel workflowId={1} />);
  view.rerender(<AgentTeamPanel workflowId={2} />);
  finishOld({ data: [run] });
  await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/api/workflows/2/team-runs'));
  expect(screen.queryByText("Labels: 23 nonzero IDs.")).not.toBeTruthy();
});

test("opens historical evidence instead of showing only its summary", async () => {
  const older = { ...run, id: "older", summary: "Earlier findings", tasks: [{ ...run.tasks[0], id: "old-task", result: { ...run.tasks[0].result, observations: ["Earlier data evidence"] } }] };
  apiClient.get.mockResolvedValue({ data: [run, older] });
  render(<AgentTeamPanel workflowId={1} projectName="NucMM" />);
  await screen.findByText("Labels: 23 nonzero IDs.");
  fireEvent.click(screen.getByText("Inspect check"));
  expect(await screen.findByText("Earlier data evidence")).toBeTruthy();
  expect(screen.queryByText("Labels: 23 nonzero IDs.")).toBeNull();
  expect(screen.getByText("NucMM")).toBeTruthy();
});

test("shows model progress and cancels the actual active run", async () => {
  const active = { ...run, executor: "local_llm", model_config: { model: "qwen3:4b" }, status: "running", phase: "planning", tasks: [], actions: [], model_calls: [{ role: "project_manager.plan", status: "running" }] };
  apiClient.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith('team-runtime') ? { enabled: true, model: 'qwen3:4b' } : [active] }));
  apiClient.post.mockResolvedValue({ data: {} });
  render(<AgentTeamPanel workflowId={1} />);
  expect(await screen.findByText("Local model · qwen3:4b")).toBeTruthy();
  expect(screen.getByText("Planning tasks…")).toBeTruthy();
  fireEvent.click(screen.getByText("Cancel task"));
  await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('/api/workflows/1/team-runs/r1/cancel'));
});

test("delivers a completed model result to the linked conversation", async () => {
  const result = { ...run, executor: 'local_llm', model_config: { model: 'qwen3:4b' } };
  apiClient.get.mockResolvedValue({ data: [result] });
  const onResult = jest.fn();
  render(<AgentTeamPanel workflowId={1} onResult={onResult} />);
  await waitFor(() => expect(onResult).toHaveBeenCalledWith(result));
  expect(screen.getByText('Agent recommendation')).toBeTruthy();
});
