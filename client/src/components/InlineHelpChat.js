import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { Button, Input, Space, Spin, Typography } from "antd";
import { QuestionCircleOutlined, SendOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import { queryTaskAgent } from "../utils/api";

const { TextArea } = Input;
const { Text } = Typography;

const buildPrompt = ({ label, yamlKey, value, projectContext, taskContext }) => {
  return [
    `Explain this setting and recommend a concrete value if possible:`,
    `- Label: ${label}`,
    yamlKey ? `- Key: ${yamlKey}` : null,
    value !== undefined ? `- Current value: ${JSON.stringify(value)}` : null,
    `- Project context: ${projectContext}`,
    `- Task context: ${taskContext}`,
    `Use plain language for non-CS users and give a recommended setting.`,
  ]
    .filter(Boolean)
    .join("\n");
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

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
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0, width: 320, height: 220 });
  const [anchorPoint, setAnchorPoint] = useState({ x: 0, y: 0 });

  const initialPrompt = useMemo(
    () =>
      buildPrompt({
        label,
        yamlKey,
        value,
        projectContext,
        taskContext,
      }),
    [label, yamlKey, value, projectContext, taskContext],
  );

  const sendMessage = async (text, options = {}) => {
    const { hideUser = false } = options;
    if (!text.trim() || isSending) return;
    setIsSending(true);
    if (!hideUser) {
      const userMessage = { text, isUser: true };
      setMessages((prev) => [...prev, userMessage]);
    }
    try {
      const res = await queryTaskAgent(
        taskKey,
        text,
        projectContext,
        taskContext,
      );
      const reply = res.response || "Sorry, I could not generate a response.";
      setMessages((prev) => [...prev, { text: reply, isUser: false }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { text: error.message || "Error contacting chatbot.", isUser: false },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const openPanel = () => {
    if (!anchorRef.current) return;
    const rect = anchorRef.current.getBoundingClientRect();
    const anchor = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;
    const width = panelPos.width || 320;
    const height = panelPos.height || 220;

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
    if (top < 16) {
      top = 16;
    }

    setAnchorPoint(anchor);
    setPanelPos((prev) => ({ ...prev, top, left }));
    setOpen(true);

    if (messages.length === 0) {
      sendMessage(initialPrompt, { hideUser: true });
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const query = inputValue;
    setInputValue("");
    await sendMessage(query);
  };

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

  const panel = open ? (
    <>
      <svg
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          pointerEvents: "none",
          zIndex: 1000,
        }}
      >
        <line
          x1={anchorPoint.x}
          y1={anchorPoint.y}
          x2={panelPos.left}
          y2={panelPos.top}
          stroke="#bfbfbf"
          strokeDasharray="4 4"
        />
      </svg>
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
          border: "1px dashed #d9d9d9",
          borderRadius: 12,
          boxShadow: "0 12px 28px rgba(0,0,0,0.12)",
          display: "flex",
          flexDirection: "column",
          resize: "both",
          overflow: "auto",
        }}
        onMouseUp={(event) => {
          const newRect = panelRef.current?.getBoundingClientRect();
          if (newRect) {
            setPanelPos((prev) => ({
              ...prev,
              width: newRect.width,
              height: newRect.height,
            }));
          }
        }}
      >
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
          }}
        >
          <span>{label}</span>
          <Button type="text" size="small" onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: "8px 12px" }}>
          {messages.map((messageItem, index) => (
            <div
              key={index}
              style={{
                marginBottom: 8,
                padding: "8px 10px",
                borderRadius: 10,
                background: messageItem.isUser ? "#e6f7ff" : "#fafafa",
              }}
            >
              {messageItem.isUser ? (
                <Text style={{ fontSize: 12 }}>{messageItem.text}</Text>
              ) : (
                <ReactMarkdown
                  components={{
                    strong: ({ children }) => (
                      <strong style={{ fontWeight: 700 }}>{children}</strong>
                    ),
                    p: ({ children }) => (
                      <p style={{ margin: 0, fontSize: 12 }}>{children}</p>
                    ),
                  }}
                >
                  {messageItem.text}
                </ReactMarkdown>
              )}
            </div>
          ))}
          {isSending && <Spin size="small" />}
        </div>
        <div style={{ padding: "8px 12px", borderTop: "1px solid #f0f0f0" }}>
          <Space.Compact style={{ width: "100%" }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask a follow-up..."
              autoSize={{ minRows: 1, maxRows: 2 }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button icon={<SendOutlined />} onClick={handleSend} />
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
      />
      {open ? ReactDOM.createPortal(panel, document.body) : null}
    </>
  );
}

export default InlineHelpChat;
