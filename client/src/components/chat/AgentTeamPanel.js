import React, { useEffect, useRef, useState } from "react";
import { Alert, Button, Select, Space, Typography } from "antd";
import { apiClient } from "../../api";

const { Text } = Typography;
const statusLabel = {
  cancelled: "Cancelled", queued: "Queued", running: "Working", completed: "Checked", blocked: "Needs input",
  failed: "Failed", needs_attention: "Needs attention", interrupted: "Interrupted",
};

export default function AgentTeamPanel({ workflowId, projectName, focusRunId, onAction, onResult }) {
  const [runtime, setRuntime] = useState(null);
  useEffect(() => {
    let active = true;
    apiClient.get("/api/workflows/team-runtime").then(({ data }) => { if (active) setRuntime(data); }).catch(() => {});
    return () => { active = false; };
  }, []);
  const panel = useRef(null);
  useEffect(() => { panel.current?.scrollIntoView?.({ block: "start" }); }, [focusRunId]);
  const [selectedId, setSelectedId] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [runs, setRuns] = useState([]);
  const [scope, setScope] = useState("project");
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const currentProject = useRef(workflowId);
  currentProject.current = workflowId;

  useEffect(() => {
    let active = true;
    let timer;
    setRuns([]);
    setSelectedId(focusRunId || null);
    setError("");
    setStarting(false);
    const refresh = async () => {
      if (!workflowId) return;
      try {
        const { data } = await apiClient.get(`/api/workflows/${workflowId}/team-runs`);
        if (active) { setRuns(data); setError(""); }
      } catch (err) {
        if (active) setError(err.response?.data?.detail || "Could not load specialist tasks.");
      } finally {
        if (active) timer = setTimeout(refresh, 2500);
      }
    };
    refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [workflowId, focusRunId]);

  const start = async () => {
    const project = workflowId;
    setStarting(true);
    setError("");
    try {
      const { data } = await apiClient.post(`/api/workflows/${project}/team-runs`, {
        scope, request_key: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      });
      if (currentProject.current === project) { setSelectedId(data.id); setRuns((old) => [data, ...old.filter((run) => run.id !== data.id)]); }
    } catch (err) {
      if (currentProject.current === project) setError(err.response?.data?.detail || "Could not start specialist tasks.");
    } finally {
      if (currentProject.current === project) setStarting(false);
    }
  };

  const latest = selectedId ? runs.find((run) => run.id === selectedId) : runs[0];
  useEffect(() => {
    if (latest && !["queued", "running"].includes(latest.status)) onResult?.(latest);
  }, [latest, onResult]);
  const cancel = async () => {
    try { await apiClient.post(`/api/workflows/${workflowId}/team-runs/${latest.id}/cancel`); }
    catch (err) { setError(err.response?.data?.detail || "Could not cancel this task."); }
  };
  const runAction = async (index) => {
    const project = workflowId;
    setExecuting(true);
    setError("");
    try {
      const { data } = await apiClient.post(`/api/workflows/${project}/team-runs/${latest.id}/actions/${index}`);
      if (currentProject.current === project) await onAction(data);
    } catch (err) {
      if (currentProject.current === project) setError(err.response?.data?.detail || err.message || "The app action could not be completed.");
    } finally {
      if (currentProject.current === project) setExecuting(false);
    }
  };
  const busy = executing || starting || runs.some((run) => ["queued", "running"].includes(run.status));
  return (
    <section ref={panel} aria-label="Project manager team" style={{ padding: 14, background: "white", border: "1px solid #ddd", borderRadius: 6, marginBottom: 16 }}>
      <Text strong>{projectName || latest?.context?.project || "Project manager"}</Text>
      <p style={{ margin: "6px 0 12px", color: "#666", fontSize: 12 }}>{latest?.executor === "local_llm" ? `Local model · ${latest.model_config?.model}` : latest ? "Tool-backed check · model reasoning was not used" : runtime?.enabled ? `Local model · ${runtime.model}` : "Tool-backed prototype · model reasoning is not enabled"}</p>
      <Space wrap>
        <Select aria-label="Specialist scope" value={scope} onChange={setScope} style={{ width: 160 }} options={[
          { value: "project", label: "Whole project" }, { value: "data", label: "Data inspection" },
          { value: "annotation", label: "Annotation review" }, { value: "model", label: "Model readiness" },
        ]} />
        <Button onClick={start} loading={busy} disabled={!workflowId || busy}>Check project</Button>
      </Space>
      {error && <Alert role="alert" type="error" message={error} style={{ marginTop: 12 }} />}
      {!latest && !error && <p>{selectedId ? "Loading requested check…" : "Delegate a check, inspect the findings, then choose the next app action."}</p>}
      {latest && <>
        <p aria-live="polite"><Text strong>{statusLabel[latest.status] || latest.status}</Text> · {new Date(latest.created_at).toLocaleTimeString()}</p>
        {latest.executor === "local_llm" && !["queued", "running"].includes(latest.status) && <Text type="secondary">Agent recommendation</Text>}
        <p>{latest.summary}</p>
        <Space wrap style={{ display: "flex", marginBottom: 8 }}>{latest.status === "running" && <Text type="secondary">{latest.phase === "planning" ? "Planning tasks…" : latest.phase === "synthesis" ? "Combining specialist findings…" : "Specialists working…"}</Text>}
        {["queued", "running"].includes(latest.status) && <Button size="small" onClick={cancel}>Cancel task</Button>}</Space>
        {latest.error && <Alert type="error" message={latest.error} />}
        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>{latest.scope ? `${latest.scope === "project" ? "Whole project" : latest.scope} check` : `${latest.tasks.length} specialist check`}</Text>
        {latest.stale && <Alert type="warning" message="Project inputs changed. Run a fresh check before using these results." />}
        <Space wrap style={{ marginBottom: 12 }}>{latest.actions?.map((action, index) => <Button size="small" key={action.query} disabled={latest.stale || busy || !onAction} onClick={() => runAction(index)}>{action.label}</Button>)}</Space>
        {latest.tasks.map((task) => <div key={task.id} style={{ borderTop: "1px solid #eee", padding: "12px 0" }}>
          <Space style={{ width: "100%", justifyContent: "space-between" }}><Text strong>{task.name}</Text><Text type={task.status === "failed" ? "danger" : "secondary"}>{statusLabel[task.status] || task.status}</Text></Space>
          {task.result?.observations?.length > 0 && <ul style={{ paddingLeft: 18, margin: "8px 0" }}>{task.result.observations.map((line, index) => <li key={index}>{line}</li>)}</ul>}
          {task.result?.blockers?.map((line, index) => <p key={index} style={{ color: "#9b3e00" }}>{line}</p>)}
          {task.error && <p role="alert">{task.error}</p>}
          <details style={{ marginTop: 8 }}><summary style={{ cursor: "pointer", color: "#666", fontSize: 12 }}>Task context and evidence</summary>
            {task.result?.interpretation && <p><strong>Model interpretation: </strong>{task.result.interpretation}</p>}
            <p>{task.goal}</p><p>Tools: {task.tools.join(", ")}</p>
            <pre style={{ fontSize: 11, whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: 220, overflow: "auto" }}>{JSON.stringify({ task_id: task.id, context: task.context, tool_calls: task.tool_calls, evidence_ids: task.result?.evidence_ids, facts: task.result?.facts, proposals: task.result?.actions }, null, 2)}</pre>
          </details>
        </div>)}
        {latest.model_calls?.length > 0 && <details><summary>Model activity ({latest.model_calls.length})</summary>
          {latest.model_calls.map((call, i) => <p key={i}>{call.role} · {call.status} · {call.seconds ?? "…"} s · {call.output_tokens ?? 0} output tokens</p>)}
          {latest.plan && <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>{JSON.stringify(latest.plan, null, 2)}</pre>}
        </details>}
        <p style={{ color: "#666", fontSize: 12 }}>These checks report artifact state, not completed scientific review or model quality.</p>
        {runs.length > 1 && <details><summary>Other checks ({runs.length - 1})</summary>{runs.filter((run) => run.id !== latest.id).map((run) => <div key={run.id} style={{ paddingTop: 8 }}><Text>{new Date(run.created_at).toLocaleString()} · {statusLabel[run.status] || run.status}{run.stale ? " · Previous context" : ""}</Text><p>{run.summary}</p><Button size="small" onClick={() => setSelectedId(run.id)}>Inspect check</Button></div>)}</details>}
      </>}
    </section>
  );
}
