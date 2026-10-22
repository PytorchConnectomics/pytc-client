import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  ThunderboltOutlined,
  RollbackOutlined,
} from "@ant-design/icons";
import { buildApiUrl, getNeuroglancerViewer } from "../api";
import "./TaskScripts.css";

const { Text, Paragraph } = Typography;
const api = (path) => buildApiUrl(`/api/task-dsl${path}`);
const ACTIVE = new Set(["submitting", "queued", "running", "unknown"]);
const STATE_COLOR = {
  queued: "gold",
  submitting: "gold",
  running: "blue",
  done: "green",
  failed: "red",
  cancelled: "default",
  unknown: "default",
};
const SOURCE_LABEL = {
  script: { text: "from your script", color: "blue" },
  "auto-fix": { text: "automatic fix", color: "orange" },
  target: { text: "where it runs", color: "purple" },
};

/* ---------- Editor: transparent textarea over a highlighted backdrop ---------- */

const tokenize = (line) => {
  const tokens = [];
  const push = (text, cls) => text && tokens.push({ text, cls });
  const hash = (() => {
    let quoted = false;
    for (let i = 0; i < line.length; i += 1) {
      if (line[i] === '"') quoted = !quoted;
      if (line[i] === "#" && !quoted) return i;
    }
    return -1;
  })();
  const code = hash >= 0 ? line.slice(0, hash) : line;
  const comment = hash >= 0 ? line.slice(hash) : "";
  const header = code.match(/^(task)(\s+)(\S+)?(\s+)?(on)?(\s+)?(\S+)?(.*)$/);
  if (header) {
    push(header[1], "kw");
    push(header[2]);
    push(header[3], "verb");
    push(header[4]);
    push(header[5], "kw");
    push(header[6]);
    push(header[7], "target");
    push(header[8]);
  } else {
    const field = code.match(/^(\s+)([A-Za-z_][\w-]*)(\s+)?(.*)$/);
    if (field) {
      push(field[1]);
      push(field[2], "field");
      push(field[3]);
      const value = field[4] || "";
      push(value, value.startsWith('"') ? "str" : /^-?[\d.]+\s*$/.test(value) ? "num" : "ident");
    } else push(code);
  }
  push(comment, "comment");
  return tokens;
};

function ScriptEditor({ value, onChange, diagnostics, editorRef }) {
  const backRef = useRef(null);
  const gutterRef = useRef(null);
  const lines = value.split("\n");
  const byLine = useMemo(() => {
    const map = {};
    const rank = { error: 3, warning: 2, info: 1 };
    diagnostics.forEach((d) => {
      if (!map[d.line] || rank[d.severity] > rank[map[d.line].severity]) map[d.line] = d;
    });
    return map;
  }, [diagnostics]);

  const syncScroll = (e) => {
    if (backRef.current) {
      backRef.current.scrollTop = e.target.scrollTop;
      backRef.current.scrollLeft = e.target.scrollLeft;
    }
    if (gutterRef.current) gutterRef.current.scrollTop = e.target.scrollTop;
  };

  const renderLine = (line, number) => {
    const diag = byLine[number];
    const tokens = tokenize(line);
    if (!diag || !diag.end_col || diag.end_col <= diag.col) {
      return tokens.map((t, i) => (
        <span key={i} className={t.cls ? `tds-${t.cls}` : undefined}>
          {t.text}
        </span>
      ));
    }
    // Split tokens at the underlined span [col, end_col).
    const start = diag.col - 1;
    const end = diag.end_col - 1;
    const out = [];
    let pos = 0;
    tokens.forEach((t, i) => {
      const tEnd = pos + t.text.length;
      const pieces = [
        [pos, Math.min(tEnd, Math.max(pos, start)), false],
        [Math.max(pos, start), Math.min(tEnd, end), true],
        [Math.max(pos, Math.min(tEnd, end)), tEnd, false],
      ];
      pieces.forEach(([a, b, mark], j) => {
        if (b <= a) return;
        const cls = [t.cls ? `tds-${t.cls}` : "", mark ? `tds-squiggle tds-squiggle-${diag.severity}` : ""]
          .join(" ")
          .trim();
        out.push(
          <span key={`${i}-${j}`} className={cls || undefined}>
            {t.text.slice(a - pos, b - pos)}
          </span>,
        );
      });
      pos = tEnd;
    });
    return out;
  };

  return (
    <div className="tds-editor">
      <div className="tds-gutter" ref={gutterRef} aria-hidden="true">
        {lines.map((_, i) => {
          const diag = byLine[i + 1];
          return (
            <div key={i} className={`tds-gutter-line ${diag ? `tds-g-${diag.severity}` : ""}`}>
              {i + 1}
            </div>
          );
        })}
      </div>
      <div className="tds-code">
        <div className="tds-backdrop" ref={backRef} aria-hidden="true">
          {lines.map((line, i) => (
            <div
              key={i}
              className={`tds-line ${byLine[i + 1] ? `tds-bg-${byLine[i + 1].severity}` : ""}`}
            >
              {renderLine(line, i + 1)}
              {"​"}
            </div>
          ))}
        </div>
        <textarea
          ref={editorRef}
          className="tds-textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onScroll={syncScroll}
          spellCheck={false}
          wrap="off"
          aria-label="Task script"
        />
      </div>
    </div>
  );
}

/* ---------- Page ---------- */

const formatMetrics = (m) => {
  if (!m || !m.prediction) return null;
  const parts = [`Dice ${m.prediction.dice}`, `IoU ${m.prediction.iou}`];
  if (m.baseline) parts.push(`baseline Dice ${m.baseline.dice} (change ${m.dice_change >= 0 ? "+" : ""}${m.dice_change})`);
  return parts.join(", ");
};

function TaskScripts() {
  const [schema, setSchema] = useState(null);
  const [request, setRequest] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [draftInfo, setDraftInfo] = useState(null);
  const [draftedScript, setDraftedScript] = useState("");
  const [script, setScript] = useState("");
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);
  const [running, setRunning] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [openLogs, setOpenLogs] = useState({});
  const [error, setError] = useState("");
  const editorRef = useRef(null);
  const checkSeq = useRef(0);

  useEffect(() => {
    axios.get(api("/schema")).then((r) => setSchema(r.data)).catch(() => {});
    axios.get(api("/jobs")).then((r) => setJobs(r.data)).catch(() => {});
  }, []);

  // Check the script shortly after every edit (syntax, meaning, and paths on the target).
  useEffect(() => {
    if (!script.trim()) {
      setResult(null);
      return undefined;
    }
    const seq = ++checkSeq.current;
    setChecking(true);
    const timer = setTimeout(async () => {
      try {
        const r = await axios.post(api("/check"), { script, check_paths: true });
        if (seq === checkSeq.current) setResult(r.data);
      } catch (e) {
        if (seq === checkSeq.current) setError(`Could not check the script: ${e.message}`);
      } finally {
        if (seq === checkSeq.current) setChecking(false);
      }
    }, 450);
    return () => clearTimeout(timer);
  }, [script]);

  // Follow active jobs.
  useEffect(() => {
    const active = jobs.filter((j) => ACTIVE.has(j.state));
    if (!active.length) return undefined;
    const timer = setInterval(async () => {
      const updates = await Promise.all(
        active.map((j) => axios.get(api(`/jobs/${j.id}`)).then((r) => r.data).catch(() => null)),
      );
      setJobs((prev) => prev.map((j) => updates.find((u) => u && u.id === j.id) || j));
    }, 4000);
    return () => clearInterval(timer);
  }, [jobs]);

  const draft = useCallback(
    async (text) => {
      const req = (text ?? request).trim();
      if (!req) return;
      setRequest(req);
      setDrafting(true);
      setError("");
      try {
        const r = await axios.post(api("/draft"), { request: req, target: "cluster" });
        setDraftInfo(r.data);
        setDraftedScript(r.data.script);
        setScript(r.data.script);
      } catch (e) {
        setError(`Could not draft a script: ${e.message}`);
      } finally {
        setDrafting(false);
      }
    },
    [request],
  );

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      const r = await axios.post(api("/run"), { script, request });
      setJobs((prev) => [r.data, ...prev]);
      setOpenLogs((prev) => ({ ...prev, [r.data.id]: true }));
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(detail?.message || `Could not start the task: ${e.message}`);
    } finally {
      setRunning(false);
    }
  };

  const cancel = async (job) => {
    try {
      const r = await axios.post(api(`/jobs/${job.id}/cancel`));
      setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, ...r.data } : j)));
    } catch (e) {
      setError(`Could not stop the job: ${e.message}`);
    }
  };

  const openViewer = async (job) => {
    const [image, label] = job.local_paths || [];
    const res = await getNeuroglancerViewer(image, label || null, [1, 1, 1]);
    const url = res?.url || res?.neuroglancer_url;
    if (url) window.open(url, "_blank");
  };

  const jumpToLine = (line) => {
    const ta = editorRef.current;
    if (!ta) return;
    const offset = script.split("\n").slice(0, line - 1).join("\n").length + (line > 1 ? 1 : 0);
    ta.focus();
    ta.setSelectionRange(offset, offset + (script.split("\n")[line - 1] || "").length);
  };

  const diagnostics = result?.diagnostics || [];
  const errors = diagnostics.filter((d) => d.severity === "error");
  const warnings = diagnostics.filter((d) => d.severity !== "error");
  const plan = result?.plan;
  const edited = script && draftedScript && script !== draftedScript;
  const root = schema?.cluster?.root || "/path/to/data";
  const examples = [
    `Can we train a model on the data I have at ${root}/synthetic?`,
    `Can you run inference using my model on the data at ${root}/synthetic/data/raw/train-02_image.h5 please?`,
    `How good is that prediction compared to the ground truth at ${root}/synthetic/data/seg/ground_truth/train-02_ground_truth.h5?`,
    `Show me ${root}/synthetic/data/raw/train-02_image.h5 with my latest prediction`,
  ];
  const canRun = plan && !errors.length && !checking && !running;

  return (
    <div className="tds-page">
      <div className="tds-head">
        <div>
          <h2 className="tds-title">Task scripts</h2>
          <Text type="secondary">
            Ask for a task in plain words. Review the drafted script, edit it if needed, then approve it to run.
          </Text>
        </div>
        {schema && (
          <Space size={6} wrap>
            <Tag color={schema.cluster.configured ? "green" : "default"}>
              Cluster: {schema.cluster.configured ? `${schema.cluster.host}, ${schema.cluster.partition}` : "not set up"}
            </Tag>
            <Tag>Drafting model: {schema.draft_model}</Tag>
          </Space>
        )}
      </div>

      {error && <Alert type="error" showIcon message={error} closable onClose={() => setError("")} />}

      <Card size="small" className="tds-card" title="1. What do you want to do?">
        <Space.Compact style={{ width: "100%" }}>
          <Input.TextArea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                draft();
              }
            }}
            autoSize={{ minRows: 1, maxRows: 4 }}
            placeholder="For example: can we train a model on the data I have at /projects/lab/data?"
            aria-label="Request"
          />
          <Button type="primary" onClick={() => draft()} loading={drafting} icon={<ThunderboltOutlined />}>
            Draft script
          </Button>
        </Space.Compact>
        <div className="tds-examples">
          {examples.map((ex) => (
            <button type="button" key={ex} className="tds-example" onClick={() => draft(ex)} disabled={drafting}>
              {ex.replace(root, "…")}
            </button>
          ))}
        </div>
      </Card>

      <div className="tds-grid">
        <Card
          size="small"
          className="tds-card"
          title="2. Review and edit the script"
          extra={
            <Space size={8}>
              {draftInfo && (
                <Text type="secondary" className="tds-meta">
                  {draftInfo.source === "llm"
                    ? `Drafted by ${draftInfo.model} in ${draftInfo.seconds} s`
                    : "Drafted by keyword rules (the AI model was unavailable)"}
                </Text>
              )}
              {edited && (
                <Tooltip title="Go back to the AI draft">
                  <Button size="small" icon={<RollbackOutlined />} onClick={() => setScript(draftedScript)}>
                    Undo my edits
                  </Button>
                </Tooltip>
              )}
            </Space>
          }
        >
          {draftInfo?.note && <Paragraph className="tds-note">AI note: {draftInfo.note}</Paragraph>}
          {script ? (
            <ScriptEditor value={script} onChange={setScript} diagnostics={diagnostics} editorRef={editorRef} />
          ) : (
            <Empty description="Your drafted script appears here. You can also type one yourself." image={Empty.PRESENTED_IMAGE_SIMPLE}>
              <Button size="small" onClick={() => setScript("task train on cluster\n  image   \"\"\n  label   \"\"\n  preset  synthetic-tiny\n  output  \"\"\n")}>
                Start an empty script
              </Button>
            </Empty>
          )}
          {script && (
            <div className="tds-status" aria-live="polite">
              {checking ? (
                <Text type="secondary">
                  <Spin size="small" /> Checking the script and its paths on the cluster…
                </Text>
              ) : errors.length ? (
                <Text type="danger">
                  <CloseCircleOutlined /> {errors.length} {errors.length === 1 ? "problem" : "problems"} to fix before running
                </Text>
              ) : result ? (
                <Text type="success">
                  <CheckCircleOutlined /> Script is valid and every input file exists
                </Text>
              ) : null}
            </div>
          )}
          {diagnostics.length > 0 && (
            <ul className="tds-diags">
              {[...errors, ...warnings].map((d, i) => (
                <li key={i}>
                  <button type="button" className={`tds-diag tds-diag-${d.severity}`} onClick={() => jumpToLine(d.line)}>
                    {d.severity === "error" ? <CloseCircleOutlined /> : <WarningOutlined />}
                    <span className="tds-diag-line">Line {d.line}</span>
                    <span>
                      {d.message} {d.hint && <span className="tds-hint">{d.hint}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card size="small" className="tds-card" title="3. What will happen">
          {plan ? (
            <>
              <Paragraph className="tds-summary">{plan.summary}</Paragraph>
              <Tabs
                size="small"
                items={[
                  {
                    key: "changes",
                    label: `Config changes (${plan.changes.length})`,
                    children: plan.changes.length ? (
                      <Table
                        size="small"
                        pagination={false}
                        rowKey="key"
                        tableLayout="fixed"
                        dataSource={plan.changes}
                        columns={[
                          { title: "Setting", dataIndex: "key", width: "27%", render: (v) => <code className="tds-key">{v}</code> },
                          {
                            title: "Change",
                            width: "33%",
                            render: (_, c) => (
                              <span className="tds-change">
                                <s>{JSON.stringify(c.old)}</s> → <b>{JSON.stringify(c.new)}</b>
                              </span>
                            ),
                          },
                          {
                            title: "Why",
                            width: "40%",
                            render: (_, c) => (
                              <span>
                                <Tag color={SOURCE_LABEL[c.source]?.color}>{SOURCE_LABEL[c.source]?.text}</Tag>
                                <span className="tds-why">{c.why}</span>
                              </span>
                            ),
                          },
                        ]}
                      />
                    ) : (
                      <Text type="secondary">This task does not change a model config.</Text>
                    ),
                  },
                  ...Object.entries(plan.files).map(([name, text]) => ({
                    key: name,
                    label: name,
                    children: <pre className="tds-pre">{text}</pre>,
                  })),
                  {
                    key: "outputs",
                    label: "Outputs",
                    children: (
                      <div>
                        {plan.command && (
                          <p>
                            <Text type="secondary">Command:</Text> <code>{plan.command}</code>
                          </p>
                        )}
                        {Object.entries(plan.outputs).map(([k, v]) => (
                          <p key={k}>
                            <Text type="secondary">{k}:</Text> <code>{v}</code>
                          </p>
                        ))}
                      </div>
                    ),
                  },
                ]}
              />
              <div className="tds-approve">
                <Button type="primary" size="large" onClick={run} disabled={!canRun} loading={running}>
                  Approve and run on the {plan.target}
                </Button>
                <Text type="secondary">
                  {plan.needs_gpu ? `Submits a 1-GPU job to the ${schema?.cluster?.partition || "cluster"} queue.` : ""}
                </Text>
              </div>
            </>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={script ? "Fix the problems in the script to see what it will do." : "Nothing to preview yet."}
            />
          )}
        </Card>
      </div>

      <Card size="small" className="tds-card" title="Runs" extra={<Text type="secondary">Every approved script is kept here</Text>}>
        {!jobs.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No runs yet." />}
        <div className="tds-jobs">
          {jobs.map((job) => (
            <div key={job.id} className="tds-job">
              <div className="tds-job-head">
                <Tag color={STATE_COLOR[job.state] || "default"}>{job.state}</Tag>
                <b>{job.summary}</b>
                <Text type="secondary" className="tds-meta">
                  {job.created}
                  {job.handle?.slurm_id ? `, Slurm job ${job.handle.slurm_id}` : ""}
                </Text>
                <span className="tds-job-actions">
                  {ACTIVE.has(job.state) && job.handle && (
                    <Button size="small" danger onClick={() => cancel(job)}>
                      Stop
                    </Button>
                  )}
                  {job.verb === "view" && job.state === "done" && (
                    <Button size="small" onClick={() => openViewer(job)}>
                      Open in Neuroglancer
                    </Button>
                  )}
                  <Button size="small" onClick={() => { setScript(job.script); setDraftedScript(job.script); setDraftInfo(null); setRequest(job.request || ""); }}>
                    Load script
                  </Button>
                  <Button size="small" type="text" onClick={() => setOpenLogs((p) => ({ ...p, [job.id]: !p[job.id] }))}>
                    {openLogs[job.id] ? "Hide details" : "Details"}
                  </Button>
                </span>
              </div>
              {job.request && <div className="tds-job-req">“{job.request}”</div>}
              {job.metrics && <div className="tds-metrics">{formatMetrics(job.metrics)}</div>}
              {job.error && <Alert type="error" message={job.error} showIcon />}
              {openLogs[job.id] && (
                <div className="tds-job-body">
                  <pre className="tds-pre tds-script-pre">{job.script}</pre>
                  {job.log && <pre className="tds-pre tds-log">{job.log.split("\n").slice(-14).join("\n")}</pre>}
                  {job.outputs &&
                    Object.entries(job.outputs).map(([k, v]) => (
                      <div key={k} className="tds-meta">
                        {k}: <code>{v}</code>
                      </div>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default TaskScripts;
