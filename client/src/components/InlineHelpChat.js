import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { Button, Input, Space, Spin, Typography } from "antd";
import { QuestionCircleOutlined, SendOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { queryHelperChat } from "../api";

const { TextArea } = Input;
const { Text } = Typography;

/**
 * Build the automatic first-message prompt that explains a field and asks the
 * helper agent for a recommendation.
 */
const buildInitialPrompt = ({
  label,
  yamlKey,
  value,
  projectContext,
  taskContext,
}) => {
  return [
    `Give concise help for this setting:`,
    `- Label: ${label}`,
    yamlKey ? `- YAML key: ${yamlKey}` : null,
    value !== undefined && value !== null && value !== ""
      ? `- Current value: ${JSON.stringify(value)}`
      : null,
    projectContext ? `- Project context: ${projectContext}` : null,
    taskContext ? `- Task context: ${taskContext}` : null,
    `Answer in at most 3 short bullets. Put the recommended action first. Do not paste documentation excerpts or headings.`,
  ]
    .filter(Boolean)
    .join("\n");
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

/**
 * A small "?" button that opens a floating, draggable chat panel connected to
 * the button by a dashed SVG line.  The panel auto-fires an initial prompt on
 * first open and lets users ask follow-up questions.
 *
 * Props:
 *   taskKey          – unique key for the helper chat session (e.g. "inference")
 *   label            – human-readable field name (e.g. "Input Image")
 *   yamlKey          – optional YAML config key (e.g. "DATASET.INPUT_IMAGE")
 *   value            – current value of the field
 *   projectContext   – short project description for the LLM
 *   taskContext       – short task description for the LLM
 */
function InlineHelpChat({
  taskKey,
  label,
  yamlKey,
  value,
  projectContext,
  taskContext,
}) {
  const anchorRef = useRef(null);
  const panelRef = useRef(null);
  const dragState = useRef({ dragging: false, offsetX: 0, offsetY: 0 });
  const messagesEndRef = useRef(null);

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [panelPos, setPanelPos] = useState({
    top: 0,
    left: 0,
    width: 340,
    height: 240,
  });

  const initialPrompt = useMemo(
    () =>
      buildInitialPrompt({
        label,
        yamlKey,
        value,
        projectContext,
        taskContext,
      }),
    [label, yamlKey, value, projectContext, taskContext],
  );

  // Build a field-context string passed to the backend so the LLM knows
  // exactly which field the user is asking about.
  const fieldContext = useMemo(() => {
    const parts = [`Field: "${label}"`];
    if (yamlKey) parts.push(`YAML key: ${yamlKey}`);
    if (taskContext) parts.push(`Task: ${taskContext}`);
    return parts.join(". ");
  }, [label, yamlKey, taskContext]);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isSending]);

  // ------- Send a message to the helper backend -------
  const sendMessage = async (text, options = {}) => {
    const { hideUser = false } = options;
    if (!text.trim() || isSending) return;
    setIsSending(true);
    if (!hideUser) {
      setMessages((prev) => [...prev, { text, isUser: true }]);
    }
    try {
      const helperTaskKey = `${taskKey}:${label}`;
      const responseText = await queryHelperChat(
        helperTaskKey,
        text,
        fieldContext,
      );
      setMessages((prev) => [
        ...prev,
        {
          text: responseText || "Sorry, I could not generate a response.",
          isUser: false,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          text: error.message || "Error contacting helper chatbot.",
          isUser: false,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  // ------- Open the floating panel -------
  const openPanel = () => {
    if (!anchorRef.current) return;
    const rect = anchorRef.current.getBoundingClientRect();
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;
    const width = panelPos.width || 360;
    const height = panelPos.height || 300;

    // Prefer placing panel to the right of the "?" icon
    let left = rect.right + 12;
    let top = rect.top - 12;
    if (left + width > viewportW) {
      left = rect.left - width - 12;
    }
    if (left < 16) {
      left = clamp(rect.left, 16, viewportW - width - 16);
    }
    if (top + height > viewportH) {
      top = clamp(viewportH - height - 16, 16, viewportH - height - 16);
    }
    if (top < 16) top = 16;

    setPanelPos((prev) => ({ ...prev, top, left }));
    setOpen(true);

    // Auto-fire the initial explainer prompt on first open
    if (messages.length === 0) {
      sendMessage(initialPrompt, { hideUser: true });
    }
  };

  // ------- Follow-up send -------
  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const query = inputValue;
    setInputValue("");
    await sendMessage(query);
  };

  // ------- Drag handling -------
  useEffect(() => {
    if (!open) return;
    const onMove = (event) => {
      if (!dragState.current.dragging) return;
      const nextLeft = clamp(
        event.clientX - dragState.current.offsetX,
        8,
        window.innerWidth - panelPos.width - 8,
      );
      const nextTop = clamp(
        event.clientY - dragState.current.offsetY,
        8,
        window.innerHeight - panelPos.height - 8,
      );
      setPanelPos((prev) => ({ ...prev, left: nextLeft, top: nextTop }));
    };
    const onUp = () => {
      dragState.current.dragging = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [open, panelPos.width, panelPos.height]);

  const startDrag = (event) => {
    if (!panelRef.current) return;
    dragState.current.dragging = true;
    dragState.current.offsetX = event.clientX - panelPos.left;
    dragState.current.offsetY = event.clientY - panelPos.top;
  };

  // Track panel resize via CSS resize: both
  const handlePanelMouseUp = () => {
    const newRect = panelRef.current?.getBoundingClientRect();
    if (newRect) {
      setPanelPos((prev) => ({
        ...prev,
        width: newRect.width,
        height: newRect.height,
      }));
    }
  };

  // ------- Render the floating panel via portal -------
  const panel = open ? (
    <>
      {/* The floating panel */}
      <div
        ref={panelRef}
        style={{
          position: "fixed",
          top: panelPos.top,
          left: panelPos.left,
          width: panelPos.width,
          height: panelPos.height,
          zIndex: 1001,
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          boxShadow: "0 10px 24px rgba(15, 23, 42, 0.14)",
          display: "flex",
          flexDirection: "column",
          resize: "none",
          overflow: "auto",
        }}
        onMouseUp={handlePanelMouseUp}
      >
        {/* Draggable header */}
        <div
          onMouseDown={startDrag}
          style={{
            cursor: "move",
            padding: "8px 12px",
            borderBottom: "1px solid #f0f0f0",
            fontWeight: 600,
            fontSize: 14,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            userSelect: "none",
          }}
        >
          <span>Help: {label}</span>
          <Button type="text" size="small" onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>

        {/* Messages area */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: "8px 12px",
          }}
        >
          {messages.map((msg, index) => (
            <div
              key={index}
              style={{
                marginBottom: 8,
                padding: "8px 10px",
                borderRadius: 10,
                background: msg.isUser
                  ? "var(--seg-accent-primary-soft, #f0efff)"
                  : "#fafafa",
              }}
            >
              {msg.isUser ? (
                <Text style={{ fontSize: 12 }}>{msg.text}</Text>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    strong: ({ children }) => (
                      <strong style={{ fontWeight: 700 }}>{children}</strong>
                    ),
                    p: ({ children }) => (
                      <p style={{ margin: 0, fontSize: 12, lineHeight: 1.6 }}>
                        {children}
                      </p>
                    ),
                    ul: ({ children }) => (
                      <ul
                        style={{
                          margin: "4px 0",
                          paddingLeft: 18,
                          fontSize: 12,
                        }}
                      >
                        {children}
                      </ul>
                    ),
                    ol: ({ children }) => (
                      <ol
                        style={{
                          margin: "4px 0",
                          paddingLeft: 18,
                          fontSize: 12,
                        }}
                      >
                        {children}
                      </ol>
                    ),
                    table: ({ children }) => (
                      <table
                        style={{
                          borderCollapse: "collapse",
                          fontSize: 11,
                          margin: "4px 0",
                          width: "100%",
                        }}
                      >
                        {children}
                      </table>
                    ),
                    th: ({ children }) => (
                      <th
                        style={{
                          border: "1px solid #e8e8e8",
                          padding: "4px 6px",
                          background: "#fafafa",
                          textAlign: "left",
                        }}
                      >
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td
                        style={{
                          border: "1px solid #e8e8e8",
                          padding: "4px 6px",
                        }}
                      >
                        {children}
                      </td>
                    ),
                    code: ({ inline, children }) =>
                      inline ? (
                        <code
                          style={{
                            background: "#f5f5f5",
                            padding: "1px 4px",
                            borderRadius: 3,
                            fontSize: 11,
                          }}
                        >
                          {children}
                        </code>
                      ) : (
                        <pre
                          style={{
                            background: "#f5f5f5",
                            padding: 8,
                            borderRadius: 6,
                            fontSize: 11,
                            overflowX: "auto",
                          }}
                        >
                          <code>{children}</code>
                        </pre>
                      ),
                  }}
                >
                  {msg.text}
                </ReactMarkdown>
              )}
            </div>
          ))}
          {isSending && (
            <div style={{ textAlign: "center", padding: 8 }}>
              <Spin size="small" />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div style={{ padding: "8px 12px", borderTop: "1px solid #f0f0f0" }}>
          <Space.Compact style={{ width: "100%" }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask a follow-up…"
              autoSize={{ minRows: 1, maxRows: 2 }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              style={{ fontSize: 12 }}
            />
            <Button
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={isSending}
            />
          </Space.Compact>
        </div>
      </div>
    </>
  ) : null;

  return (
    <>
      <Button
        ref={anchorRef}
        type="text"
        size="small"
        icon={<QuestionCircleOutlined />}
        onClick={() => (open ? setOpen(false) : openPanel())}
        aria-label={`Help for ${label}`}
        style={{ color: "#8c8c8c" }}
      />
      {open ? ReactDOM.createPortal(panel, document.body) : null}
    </>
  );
}

export default InlineHelpChat;
