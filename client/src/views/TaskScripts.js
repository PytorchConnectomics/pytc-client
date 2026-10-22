import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { buildApiUrl, getNeuroglancerViewer } from "../api";
import "./TaskScripts.css";

const api = (path) => buildApiUrl(`/api/task-dsl${path}`);
const ACTIVE = new Set(["submitting", "queued", "running", "unknown"]);
const LINE_H = 22;
const EDITOR_PAD = 10;
const STATE_TEXT = {
  submitting: "Submitting",
  queued: "Queued",
  running: "Running",
  done: "Done",
  failed: "Failed",
  cancelled: "Stopped",
  unknown: "Unknown",
};

/* ---------- Helpers ---------- */

const tokenize = (line) => {
  const tokens = [];
  const push = (text, cls) => text && tokens.push({ text, cls });
  let hash = -1;
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] === '"') quoted = !quoted;
    if (line[i] === "#" && !quoted) {
      hash = i;
      break;
    }
  }
  const code = hash >= 0 ? line.slice(0, hash) : line;
  const header = code.match(/^(task)(\s+)(\S+)?(\s+)?(on)?(\s+)?(\S+)?(.*)$/);
  const setLine = code.match(/^(\s+)(set)(\s+)(\S+)(\s+)?(.*)$/);
  const field = code.match(/^(\s+)([A-Za-z_][\w-]*)(\s+)?(.*)$/);
  if (header) {
    push(header[1], "kw");
    push(header[2]);
    push(header[3], "verb");
    push(header[4]);
    push(header[5], "kw");
    push(header[6]);
    push(header[7], "target");
    push(header[8]);
  } else if (setLine) {
    push(setLine[1]);
    push(setLine[2], "kw");
    push(setLine[3]);
    push(setLine[4], "key");
    push(setLine[5]);
    push(setLine[6], "num");
  } else if (field) {
    push(field[1]);
    push(field[2], "field");
    push(field[3]);
    const value = field[4] || "";
    push(value, value.startsWith('"') ? "str" : /^-?[\d.]+\s*$/.test(value) ? "num" : "ident");
  } else push(code);
  if (hash >= 0) push(line.slice(hash), "comment");
  return tokens;
};

const lineDiff = (before, after) => {
  const a = before.replace(/\n$/, "").split("\n");
  const b = after.replace(/\n$/, "").split("\n");
  const dp = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1)
    for (let j = b.length - 1; j >= 0; j -= 1)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const ops = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      ops.push({ t: " ", s: a[i] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) ops.push({ t: "-", s: a[i++] });
    else ops.push({ t: "+", s: b[j++] });
  }
  while (i < a.length) ops.push({ t: "-", s: a[i++] });
  while (j < b.length) ops.push({ t: "+", s: b[j++] });
  return ops;
};

const upsertSetLine = (script, key, valueText) => {
  const lines = script.replace(/\n+$/, "").split("\n");
  const re = new RegExp(`^\\s+set\\s+${key.replace(/\./g, "\\.")}(\\s|$)`);
  const at = lines.findIndex((l) => re.test(l));
  const line = `  set ${key} ${valueText}`;
  if (at >= 0) lines[at] = line;
  else lines.push(line);
  return `${lines.join("\n")}\n`;
};

// Turn a block-style YAML dump into rows with full dotted keys for leaf values.
const yamlRows = (text) => {
  const stack = [];
  return text.replace(/\n$/, "").split("\n").map((raw) => {
    const m = raw.match(/^(\s*)([A-Za-z_][\w]*):(?:\s(.*))?$/);
    if (!m) return { raw };
    const depth = m[1].length / 2;
    stack.length = depth;
    stack[depth] = m[2];
    const value = m[3];
    if (value === undefined || value === "") return { raw, parent: true };
    return { raw, key: stack.slice(0, depth + 1).join("."), indent: m[1], name: m[2], value };
  });
};

const short = (value) => {
  if (typeof value === "string" && value.startsWith("/")) {
    const parts = value.split("/").filter(Boolean);
    return parts.length > 3 ? `…/${parts.slice(-3).join("/")}` : value;
  }
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 46 ? `${text.slice(0, 44)}…` : text;
};

// Render `code` spans in checker and AI messages as inline code.
const withCode = (text) =>
  String(text || "")
    .split(/(`[^`]+`)/)
    .map((part, i) => (part.startsWith("`") && part.endsWith("`") && part.length > 2 ? <code key={i}>{part.slice(1, -1)}</code> : part));

const formatMetrics = (m) => {
  if (!m || !m.prediction) return null;
  let text = `Dice ${m.prediction.dice}, IoU ${m.prediction.iou}`;
  if (m.baseline) text += ` (baseline Dice ${m.baseline.dice}, change ${m.dice_change >= 0 ? "+" : ""}${m.dice_change})`;
  return text;
};

/* ---------- Script editor with a line-aligned margin ---------- */

function ScriptEditor({ value, onChange, notes, editorRef }) {
  const lines = value.split("\n");
  const marginRef = useRef(null);
  const byLine = useMemo(() => {
    const map = {};
    const rank = { error: 3, warning: 2, answer: 1 };
    notes.forEach((n) => {
      if (!map[n.line] || rank[n.kind] > rank[map[n.line].kind]) map[n.line] = n;
    });
    return map;
  }, [notes]);
  const sorted = useMemo(() => [...notes].sort((a, b) => a.line - b.line || (a.kind === "error" ? -1 : 1)), [notes]);

  // Place each margin note level with its line, pushing later notes down so none overlap.
  useLayoutEffect(() => {
    const el = marginRef.current;
    if (!el) return;
    let floor = 0;
    Array.from(el.children).forEach((child) => {
      const line = Number(child.dataset.line) || 1;
      const top = Math.max(EDITOR_PAD + (line - 1) * LINE_H - 1, floor);
      child.style.top = `${top}px`;
      floor = top + child.offsetHeight + 6;
    });
    el.style.minHeight = `${floor}px`;
  }, [sorted, value]);

  const renderLine = (line, number) => {
    const note = byLine[number];
    const tokens = tokenize(line);
    const mark = note && note.kind !== "answer" && note.end_col > note.col ? [note.col - 1, note.end_col - 1] : null;
    let pos = 0;
    return tokens.flatMap((t, i) => {
      const start = pos;
      const end = pos + t.text.length;
      pos = end;
      const cls = t.cls ? `ts-tk-${t.cls}` : "";
      if (!mark || mark[1] <= start || mark[0] >= end) return [<span key={i} className={cls || undefined}>{t.text}</span>];
      const a = Math.max(start, mark[0]);
      const b = Math.min(end, mark[1]);
      return [
        <span key={`${i}a`} className={cls || undefined}>{t.text.slice(0, a - start)}</span>,
        <span key={`${i}b`} className={`${cls} ts-squiggle ts-squiggle-${note.kind}`}>{t.text.slice(a - start, b - start)}</span>,
        <span key={`${i}c`} className={cls || undefined}>{t.text.slice(b - start)}</span>,
      ];
    });
  };

  return (
    <div className={`ts-editor-row ${sorted.length ? "has-notes" : ""}`}>
      <div className="ts-editor" style={{ height: lines.length * LINE_H + EDITOR_PAD * 2 + 14 }}>
        <div className="ts-gutter" aria-hidden="true">
          {lines.map((_, i) => (
            <div key={i} className={`ts-gutter-line ${byLine[i + 1] ? `ts-g-${byLine[i + 1].kind}` : ""}`}>
              {i + 1}
            </div>
          ))}
        </div>
        <div className="ts-code">
          <div className="ts-backdrop" aria-hidden="true">
            {lines.map((line, i) => (
              <div key={i} className={`ts-line ${byLine[i + 1] ? `ts-line-${byLine[i + 1].kind}` : ""}`}>
                {renderLine(line, i + 1)}
                {"​"}
              </div>
            ))}
          </div>
          <textarea
            ref={editorRef}
            className="ts-textarea"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onScroll={(e) => {
              e.target.previousSibling.scrollLeft = e.target.scrollLeft;
            }}
            spellCheck={false}
            wrap="off"
            aria-label="Task script"
          />
        </div>
      </div>
      <div className="ts-margin" ref={marginRef} aria-label="Notes on the script" hidden={!sorted.length}>
        {sorted.map((n, i) => (
          <div key={`${n.line}-${i}`} data-line={n.line} className={`ts-note ts-note-${n.kind}`}>
            <span className="ts-note-where">
              {n.kind === "answer" ? "AI" : n.kind === "error" ? "Problem" : "Note"}, line {n.line}
            </span>
            <span className="ts-note-text">{withCode(n.message)}</span>
            {n.hint && <span className="ts-note-hint">{withCode(n.hint)}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- Page ---------- */

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
  const [openJob, setOpenJob] = useState(null);
  const [error, setError] = useState("");
  const [thread, setThread] = useState([]);
  const [message, setMessage] = useState("");
  const [asking, setAsking] = useState(false);
  const [answerNote, setAnswerNote] = useState(null);
  const [showYaml, setShowYaml] = useState(false);
  const [editingKey, setEditingKey] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [editOriginal, setEditOriginal] = useState("");
  const editorRef = useRef(null);
  const threadEndRef = useRef(null);
  const checkSeq = useRef(0);

  useEffect(() => {
    axios.get(api("/schema")).then((r) => setSchema(r.data)).catch(() => {});
    axios.get(api("/jobs")).then((r) => setJobs(r.data)).catch(() => {});
  }, []);

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

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [thread]);

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
        setThread([]);
        setAnswerNote(null);
      } catch (e) {
        setError(`Could not draft a script: ${e.message}`);
      } finally {
        setDrafting(false);
      }
    },
    [request],
  );

  const ask = async () => {
    const text = message.trim();
    if (!text || !script) return;
    const priorThread = thread.map((t) => ({ role: t.role, text: t.text }));
    // Follow-ups build on a proposal that is still waiting for review, so "also …" stacks.
    const pending = [...thread].reverse().find((t) => t.proposal && t.status === "open");
    const workingScript = pending ? pending.proposal : script;
    setThread((prev) => [...prev.map((t) => (t === pending ? { ...t, status: "merged" } : t)), { role: "user", text }]);
    setMessage("");
    setAsking(true);
    try {
      const r = await axios.post(api("/converse"), {
        request,
        script: workingScript,
        message: text,
        thread: priorThread,
        draft_note: draftInfo?.note || "",
      });
      const d = r.data;
      setThread((prev) => [
        ...prev,
        { role: "ai", text: d.reply, kind: d.kind, line: d.line, proposal: d.script, base: script, problems: d.problems || [], steps: d.steps || [], status: "open" },
      ]);
      setAnswerNote(d.kind === "answer" && d.line ? { line: d.line, message: d.reply } : null);
    } catch (e) {
      setThread((prev) => [...prev, { role: "ai", kind: "error", text: `Could not reach the server: ${e.message}` }]);
    } finally {
      setAsking(false);
    }
  };

  const resolveProposal = (index, accept) => {
    setThread((prev) =>
      prev.map((t, i) => {
        if (i !== index) return t;
        if (accept) setScript(t.proposal);
        return { ...t, status: accept ? "accepted" : "discarded" };
      }),
    );
  };

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      const r = await axios.post(api("/run"), { script, request });
      setJobs((prev) => [r.data, ...prev]);
      setOpenJob(r.data.id);
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

  const loadJob = (job) => {
    setScript(job.script);
    setDraftedScript(job.script);
    setDraftInfo(null);
    setRequest(job.request || "");
    setThread([]);
    setAnswerNote(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const commitYamlEdit = () => {
    const next = editValue.trim();
    if (editingKey && next && next !== editOriginal.trim()) setScript((s) => upsertSetLine(s, editingKey, next));
    setEditingKey(null);
  };

  const diagnostics = result?.diagnostics || [];
  const errors = diagnostics.filter((d) => d.severity === "error");
  const plan = result?.plan;
  const notes = [
    ...diagnostics.map((d) => ({ line: d.line, kind: d.severity === "error" ? "error" : "warning", message: d.message, hint: d.hint, col: d.col, end_col: d.end_col })),
    ...(answerNote ? [{ ...answerNote, kind: "answer" }] : []),
  ];
  const edited = script && draftedScript && script !== draftedScript;
  const root = schema?.cluster?.root || "/path/to/data";
  const managed = new Set(schema?.managed_keys?.[plan?.verb] || []);
  const examples = [
    ["Train", `Can we train a model on the data I have at ${root}/synthetic?`],
    ["Run my model", `Can you run inference using my model on the data at ${root}/synthetic/data/raw/train-02_image.h5 please?`],
    ["Score it", `How good is that prediction compared to the ground truth at ${root}/synthetic/data/seg/ground_truth/train-02_ground_truth.h5?`],
    ["View it", `Show me ${root}/synthetic/data/raw/train-02_image.h5 with my latest prediction`],
  ];
  let runHint = "";
  if (!script) runHint = "Draft or write a script first.";
  else if (checking) runHint = "Checking the script…";
  else if (errors.length) runHint = `Fix ${errors.length === 1 ? "the problem" : `${errors.length} problems`} in the script first.`;
  const canRun = plan && !errors.length && !checking && !running;

  return (
    <div className="ts-page">
      <header className="ts-head">
        <div>
          <h1 className="ts-title">Task scripts</h1>
          <p className="ts-lede">Ask for a task in plain words. Nothing runs until you have read the script and pressed Run.</p>
        </div>
        {schema && (
          <dl className="ts-env">
            <div>
              <dt>Runs on</dt>
              <dd>{schema.cluster.configured ? `${schema.cluster.host}, ${schema.cluster.partition} queue` : "cluster not set up"}</dd>
            </div>
            <div>
              <dt>Drafted by</dt>
              <dd>{schema.draft_model}</dd>
            </div>
          </dl>
        )}
      </header>

      {error && (
        <div className="ts-alert" role="alert">
          {error}
          <button type="button" onClick={() => setError("")}>Dismiss</button>
        </div>
      )}

      <form
        className="ts-ask"
        onSubmit={(e) => {
          e.preventDefault();
          draft();
        }}
      >
        <label htmlFor="ts-request" className="ts-sr">Request</label>
        <input
          id="ts-request"
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          placeholder="Can we train a model on the data I have at /projects/lab/data?"
          autoComplete="off"
        />
        <button type="submit" className="ts-btn ts-btn-dark" disabled={drafting || !request.trim()}>
          {drafting ? "Drafting…" : "Draft script"}
        </button>
      </form>
      <div className="ts-examples">
        <span>Try:</span>
        {examples.map(([label, text]) => (
          <button type="button" key={label} onClick={() => draft(text)} disabled={drafting} title={text}>
            {label}
          </button>
        ))}
      </div>

      <div className="ts-main">
        <section className="ts-sheet" aria-label="Script">
          <div className="ts-sheet-head">
            <h2>Script</h2>
            <div className="ts-sheet-meta">
              {draftInfo && (
                <span>
                  {draftInfo.source === "llm"
                    ? `Drafted in ${draftInfo.seconds} s`
                    : "Drafted by keyword rules, since the AI model was unavailable"}
                </span>
              )}
              {edited && (
                <button type="button" className="ts-link" onClick={() => setScript(draftedScript)}>
                  Revert to the draft
                </button>
              )}
            </div>
          </div>

          {script ? (
            <>
              {draftInfo?.note && !edited && <p className="ts-draft-note">{withCode(draftInfo.note)}</p>}
              <ScriptEditor value={script} onChange={setScript} notes={notes} editorRef={editorRef} />
              <p className={`ts-check ${errors.length ? "is-bad" : result && !checking ? "is-good" : ""}`} aria-live="polite">
                {checking
                  ? "Checking the script and its files on the cluster…"
                  : errors.length
                    ? `${errors.length} ${errors.length === 1 ? "problem" : "problems"} to fix. Each one is noted next to its line.`
                    : result
                      ? "The script is valid and every input file exists."
                      : ""}
              </p>

              <div className="ts-thread" aria-label="Conversation about this script">
                {thread.map((t, i) => (
                  <div key={i} className={`ts-turn ts-turn-${t.role}`}>
                    {t.role === "user" ? (
                      <p className="ts-said">{t.text}</p>
                    ) : (
                      <div className="ts-reply">
                        <p className={t.kind === "error" ? "ts-reply-error" : undefined}>
                          {withCode(t.text)}
                          {t.kind === "answer" && t.line ? <span className="ts-reply-line"> (line {t.line})</span> : null}
                        </p>
                        {t.steps?.length > 0 && (
                          <ol className="ts-steps" aria-label="What the assistant did">
                            {t.steps.map((st, k) => (
                              <li key={k} className={st.ok ? undefined : "is-miss"}>
                                {withCode(st.text)}
                              </li>
                            ))}
                          </ol>
                        )}
                        {t.proposal && (
                          <div className={`ts-proposal is-${t.status}`}>
                            <pre className="ts-diff">
                              {lineDiff(t.base, t.proposal).map((op, k) =>
                                op.t === " " ? null : (
                                  <div key={k} className={op.t === "+" ? "ts-add" : "ts-del"}>
                                    <span aria-hidden="true">{op.t}</span>
                                    {op.s}
                                  </div>
                                ),
                              )}
                            </pre>
                            {t.problems.length > 0 && (
                              <p className="ts-proposal-warn">
                                This version has {t.problems.length} {t.problems.length === 1 ? "problem" : "problems"}: {t.problems[0].message}
                              </p>
                            )}
                            {t.status === "open" ? (
                              <div className="ts-proposal-actions">
                                <button type="button" className="ts-btn ts-btn-dark" onClick={() => resolveProposal(i, true)}>
                                  Accept change
                                </button>
                                <button type="button" className="ts-btn" onClick={() => resolveProposal(i, false)}>
                                  Discard
                                </button>
                              </div>
                            ) : (
                              <p className="ts-proposal-done">
                                {{ accepted: "Accepted into the script.", discarded: "Discarded.", merged: "Included in the next proposal below." }[t.status]}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {asking && <p className="ts-thinking">Working on it…</p>}
                <div ref={threadEndRef} />
              </div>
              <form
                className="ts-say"
                onSubmit={(e) => {
                  e.preventDefault();
                  ask();
                }}
              >
                <label htmlFor="ts-message" className="ts-sr">Ask about the script or say what to change</label>
                <input
                  id="ts-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Ask why it chose something, or say what to change"
                  autoComplete="off"
                  disabled={asking}
                />
                <button type="submit" className="ts-btn" disabled={asking || !message.trim()}>
                  Send
                </button>
              </form>
            </>
          ) : (
            <div className="ts-empty">
              <p>Your drafted script appears here. You can also write one yourself.</p>
              <button
                type="button"
                className="ts-link"
                onClick={() =>
                  setScript('task train on cluster\n  image   ""\n  label   ""\n  preset  synthetic-tiny\n  steps   100\n  output  ""\n')
                }
              >
                Start a blank training script
              </button>
            </div>
          )}
        </section>

        <aside className="ts-plan" aria-label="Before it runs">
          <h2>Before it runs</h2>
          {plan ? (
            <>
              <p className="ts-plan-summary">{plan.summary}</p>
              {[
                ["From your script", plan.changes.filter((c) => c.source !== "auto-fix")],
                ["Automatic fixes", plan.changes.filter((c) => c.source === "auto-fix")],
              ].map(([title, group]) =>
                group.length ? (
                  <div key={title} className="ts-change-group">
                    <h3>{title}</h3>
                    <ul className="ts-changes">
                      {group.map((c) => (
                        <li key={c.key} className={`ts-change is-${c.source}`}>
                          <code className="ts-change-key">{c.key}</code>
                          <span className="ts-change-val">
                            <del>{short(c.old)}</del> <ins>{short(c.new)}</ins>
                          </span>
                          {(c.source !== "script" || c.why.startsWith("`set`")) && <span className="ts-change-why">{c.why}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null,
              )}
              {Object.entries(plan.files).map(([name, text]) => (
                <div key={name} className="ts-file">
                  <button type="button" className="ts-link" onClick={() => setShowYaml((v) => !v)} aria-expanded={showYaml}>
                    {showYaml ? `Hide ${name}` : `Show ${name}`}
                  </button>
                  {showYaml && name === "config.yaml" && (
                    <>
                      <p className="ts-file-help">Click a value to change it. The change is added to the script as a set line.</p>
                      <div className="ts-yaml" role="list">
                        {yamlRows(text).map((row, i) => {
                          if (!row.key || managed.has(row.key)) {
                            return (
                              <div key={i} role="listitem" className={`ts-yaml-row ${row.parent ? "is-parent" : "is-fixed"}`}>
                                {row.raw}
                              </div>
                            );
                          }
                          return (
                            <div key={i} role="listitem" className="ts-yaml-row">
                              {row.indent}
                              {row.name}:{" "}
                              {editingKey === row.key ? (
                                <input
                                  className="ts-yaml-input"
                                  autoFocus
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onBlur={commitYamlEdit}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") commitYamlEdit();
                                    if (e.key === "Escape") setEditingKey(null);
                                  }}
                                  aria-label={`New value for ${row.key}`}
                                />
                              ) : (
                                <button
                                  type="button"
                                  className="ts-yaml-value"
                                  onClick={() => {
                                    setEditingKey(row.key);
                                    setEditValue(row.value);
                                    setEditOriginal(row.value);
                                  }}
                                  title={`Change ${row.key}`}
                                >
                                  {row.value}
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                  {showYaml && name !== "config.yaml" && <pre className="ts-pre">{text}</pre>}
                </div>
              ))}
              <dl className="ts-outputs">
                {Object.entries(plan.outputs).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <p className="ts-plan-empty">
              {script ? "Once the script has no problems, this shows exactly what will change and run." : "Nothing to run yet."}
            </p>
          )}
          <button type="button" className="ts-run" onClick={run} disabled={!canRun}>
            {running ? "Submitting…" : `Run on ${plan?.target === "laptop" ? "this laptop" : "the cluster"}`}
          </button>
          <p className="ts-run-hint">
            {runHint || (plan?.needs_gpu ? `Submits a one-GPU job to the ${schema?.cluster?.partition || "cluster"} queue.` : "")}
          </p>
        </aside>
      </div>

      <section className="ts-runs" aria-label="Runs">
        <h2>Runs</h2>
        {!jobs.length && <p className="ts-plan-empty">Approved scripts and their results are kept here.</p>}
        {jobs.length > 0 && (
          <ul className="ts-ledger">
            {jobs.map((job) => (
              <li key={job.id} className="ts-run-row">
                <div className="ts-run-line">
                  <span className={`ts-state is-${job.state}`}>{STATE_TEXT[job.state] || job.state}</span>
                  <span className="ts-run-what">
                    {job.summary}
                    {job.metrics && <span className="ts-metrics">{formatMetrics(job.metrics)}</span>}
                  </span>
                  <span className="ts-run-when">
                    {job.created.slice(11, 16)}
                    {job.handle?.slurm_id ? `, job ${job.handle.slurm_id}` : ""}
                  </span>
                  <span className="ts-run-actions">
                    {ACTIVE.has(job.state) && job.handle && (
                      <button type="button" className="ts-link is-danger" onClick={() => cancel(job)}>Stop</button>
                    )}
                    {job.verb === "view" && job.state === "done" && (
                      <button type="button" className="ts-link" onClick={() => openViewer(job)}>Open viewer</button>
                    )}
                    <button type="button" className="ts-link" onClick={() => loadJob(job)}>Edit a copy</button>
                    <button
                      type="button"
                      className="ts-link"
                      aria-expanded={openJob === job.id}
                      onClick={() => {
                        setOpenJob((o) => (o === job.id ? null : job.id));
                        if (openJob !== job.id && !job.log && job.handle) {
                          axios
                            .get(api(`/jobs/${job.id}`))
                            .then((r) => setJobs((prev) => prev.map((j) => (j.id === job.id ? r.data : j))))
                            .catch(() => {});
                        }
                      }}
                    >
                      {openJob === job.id ? "Hide" : "Details"}
                    </button>
                  </span>
                </div>
                {job.error && <p className="ts-run-error">{job.error}</p>}
                {openJob === job.id && (
                  <div className="ts-run-detail">
                    {job.request && <p className="ts-run-request">Asked: {job.request}</p>}
                    <div className="ts-run-cols">
                      <pre className="ts-pre">{job.script}</pre>
                      {job.log ? (
                        <pre className="ts-pre ts-log">{job.log.split("\n").slice(-14).join("\n")}</pre>
                      ) : (
                        <p className="ts-plan-empty">{ACTIVE.has(job.state) ? "Waiting for the first log lines…" : "No log for this run."}</p>
                      )}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default TaskScripts;
