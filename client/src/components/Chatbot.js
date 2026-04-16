import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  Button,
  Input,
  List,
  Typography,
  Space,
  Spin,
  Popconfirm,
  Tooltip,
} from "antd";
import {
  SendOutlined,
  CloseOutlined,
  DeleteOutlined,
  PlusOutlined,
  MessageOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import {
  queryChatBot,
  clearChat,
  listConversations,
  getConversation,
  deleteConversation,
} from "../api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import WorkflowTimeline from "./WorkflowTimeline";
import { useWorkflow } from "../contexts/WorkflowContext";

const { TextArea } = Input;
const { Text } = Typography;

const GREETING = {
  role: "assistant",
  content:
    "Hello! I'm your AI assistant, built to help you navigate PyTC Client. How can I help you today?",
};

/* ─── helper: truncate a string to `n` chars ─────────────────────────────── */
const truncate = (str, n = 50) =>
  str.length > n ? str.slice(0, n).trimEnd() + "…" : str;

const WORKFLOW_QUERY_TERMS = [
  "workflow",
  "next",
  "stage",
  "retrain",
  "training",
  "corrected",
  "proofread",
  "mask",
  "inference",
  "visualize",
  "evaluate",
];

/* ═══════════════════════════════════════════════════════════════════════════ */

function Chatbot({ onClose }) {
  /* ── state ─────────────────────────────────────────────────────────────── */
  const [conversations, setConversations] = useState([]);
  const [activeConvoId, setActiveConvoId] = useState(null);
  const [messages, setMessages] = useState([GREETING]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isLoadingConvo, setIsLoadingConvo] = useState(false);

  const lastMessageRef = useRef(null);
  const workflowContext = useWorkflow();

  const shouldUseWorkflowAgent = (query) => {
    if (!workflowContext?.workflow?.id || !workflowContext?.queryAgent) {
      return false;
    }
    const lower = query.toLowerCase();
    return WORKFLOW_QUERY_TERMS.some((term) => lower.includes(term));
  };

  /* ── scroll ────────────────────────────────────────────────────────────── */
  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      lastMessageRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 0);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSending, scrollToBottom]);

  /* ── load conversation list on mount ────────────────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const convos = await listConversations();
        if (!cancelled && convos) setConversations(convos);
      } catch {
        // server may not be ready yet
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* ── switch conversation ───────────────────────────────────────────────── */
  const loadConversation = async (convoId) => {
    if (convoId === activeConvoId) return;
    setIsLoadingConvo(true);
    try {
      const convo = await getConversation(convoId);
      if (!convo) return;
      await clearChat(); // reset LangChain in-memory state
      setActiveConvoId(convo.id);
      const dbMessages =
        convo.messages?.map((m) => ({ role: m.role, content: m.content })) ??
        [];
      setMessages([GREETING, ...dbMessages]);
    } finally {
      setIsLoadingConvo(false);
    }
  };

  /* ── new chat ──────────────────────────────────────────────────────────── */
  const handleNewChat = async () => {
    await clearChat();
    setActiveConvoId(null);
    setMessages([GREETING]);
    setInputValue("");
  };

  /* ── send message ──────────────────────────────────────────────────────── */
  const handleSendMessage = async () => {
    if (!inputValue.trim() || isSending) return;
    const query = inputValue;
    setInputValue("");
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setIsSending(true);
    try {
      if (shouldUseWorkflowAgent(query)) {
        const data = await workflowContext.queryAgent(query);
        const response =
          data?.response ||
          "I could not inspect the workflow state for that request.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: response },
        ]);
        return;
      }

      const data = await queryChatBot(query, activeConvoId);
      const response =
        data?.response || "Sorry, I could not generate a response.";
      const returnedConvoId = data?.conversationId ?? activeConvoId;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response },
      ]);

      // If this was the first message in a brand-new chat, we now have a convoId
      if (!activeConvoId && returnedConvoId) {
        setActiveConvoId(returnedConvoId);
      }

      // Refresh sidebar so the new / updated conversation appears
      const convos = await listConversations();
      if (convos) setConversations(convos);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: e.message || "Error contacting chatbot.",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  /* ── delete conversation ───────────────────────────────────────────────── */
  const handleDeleteConvo = async (convoId, e) => {
    if (e) e.stopPropagation();
    await deleteConversation(convoId);
    setConversations((prev) => prev.filter((c) => c.id !== convoId));
    if (activeConvoId === convoId) {
      await handleNewChat();
    }
  };

  /* ── markdown renderers ────────────────────────────────────────────────── */
  const mdComponents = {
    ul: ({ children }) => (
      <ul style={{ paddingLeft: "20px", margin: "8px 0" }}>{children}</ul>
    ),
    ol: ({ children }) => (
      <ol style={{ paddingLeft: "20px", margin: "8px 0" }}>{children}</ol>
    ),
    table: ({ children }) => (
      <div style={{ overflowX: "auto", margin: "8px 0" }}>
        <table
          style={{
            borderCollapse: "collapse",
            width: "100%",
            fontSize: "13px",
          }}
        >
          {children}
        </table>
      </div>
    ),
    thead: ({ children }) => (
      <thead style={{ backgroundColor: "#e8e8e8" }}>{children}</thead>
    ),
    th: ({ children }) => (
      <th
        style={{
          border: "1px solid #ddd",
          padding: "6px 8px",
          textAlign: "left",
          fontWeight: 600,
        }}
      >
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td style={{ border: "1px solid #ddd", padding: "6px 8px" }}>
        {children}
      </td>
    ),
    code: ({ inline, children }) =>
      inline ? (
        <code
          style={{
            backgroundColor: "#e8e8e8",
            padding: "2px 4px",
            borderRadius: "3px",
            fontSize: "12px",
          }}
        >
          {children}
        </code>
      ) : (
        <pre
          style={{
            backgroundColor: "#1e1e1e",
            color: "#d4d4d4",
            padding: "8px",
            borderRadius: "4px",
            overflowX: "auto",
            fontSize: "12px",
            margin: "8px 0",
          }}
        >
          <code>{children}</code>
        </pre>
      ),
    pre: ({ children }) => <>{children}</>,
  };

  /* ═══════════════════════════════════════════════════════════════════════ */
  /* RENDER                                                                 */
  /* ═══════════════════════════════════════════════════════════════════════ */
  return (
    <div style={{ height: "100vh", display: "flex" }}>
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      {sidebarOpen && (
        <div
          style={{
            width: 220,
            minWidth: 220,
            borderRight: "1px solid #f0f0f0",
            display: "flex",
            flexDirection: "column",
            background: "#fafafa",
          }}
        >
          {/* header */}
          <div
            style={{
              padding: "12px 10px 8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Text strong style={{ fontSize: 13 }}>
              Chats
            </Text>
            <Space size={4}>
              <Tooltip title="New chat">
                <Button
                  type="text"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={handleNewChat}
                />
              </Tooltip>
              <Tooltip title="Collapse sidebar">
                <Button
                  type="text"
                  size="small"
                  icon={<MenuFoldOutlined />}
                  onClick={() => setSidebarOpen(false)}
                />
              </Tooltip>
            </Space>
          </div>

          {/* conversation list */}
          <div style={{ flex: 1, overflowY: "auto", padding: "0 6px 8px" }}>
            {conversations.length === 0 && (
              <Text
                type="secondary"
                style={{
                  display: "block",
                  textAlign: "center",
                  padding: "24px 8px",
                  fontSize: 12,
                }}
              >
                No past chats yet
              </Text>
            )}
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => loadConversation(c.id)}
                style={{
                  padding: "8px",
                  margin: "2px 0",
                  borderRadius: 6,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background:
                    c.id === activeConvoId ? "#e6f4ff" : "transparent",
                  border:
                    c.id === activeConvoId
                      ? "1px solid #91caff"
                      : "1px solid transparent",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  if (c.id !== activeConvoId)
                    e.currentTarget.style.background = "#f0f0f0";
                }}
                onMouseLeave={(e) => {
                  if (c.id !== activeConvoId)
                    e.currentTarget.style.background = "transparent";
                }}
              >
                <MessageOutlined
                  style={{ fontSize: 13, color: "#999", flexShrink: 0 }}
                />
                <Text
                  ellipsis
                  style={{ flex: 1, fontSize: 13, lineHeight: "18px" }}
                >
                  {truncate(c.title)}
                </Text>
                <Popconfirm
                  title="Delete this conversation?"
                  onConfirm={(e) => handleDeleteConvo(c.id, e)}
                  onCancel={(e) => e?.stopPropagation()}
                  okText="Delete"
                  cancelText="Cancel"
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      flexShrink: 0,
                      opacity: 0.4,
                      transition: "opacity 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.opacity = "0.4")
                    }
                  />
                </Popconfirm>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Main chat area ──────────────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        {/* header */}
        <div
          style={{
            padding: "16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <Space>
            {!sidebarOpen && (
              <Tooltip title="Show conversations">
                <Button
                  type="text"
                  size="small"
                  icon={<MenuUnfoldOutlined />}
                  onClick={() => setSidebarOpen(true)}
                />
              </Tooltip>
            )}
            <Text strong>AI Assistant</Text>
          </Space>
          <Space>
            <Tooltip title="New chat">
              <Button
                type="text"
                icon={<PlusOutlined />}
                onClick={handleNewChat}
                size="small"
              />
            </Tooltip>
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={onClose}
              size="small"
            />
          </Space>
        </div>

        <WorkflowTimeline />

        {/* messages */}
        <div style={{ flex: 1, overflow: "auto", padding: "0 16px 16px" }}>
          {isLoadingConvo ? (
            <div style={{ textAlign: "center", padding: 40 }}>
              <Spin />
            </div>
          ) : (
            <List
              dataSource={messages}
              renderItem={(message, index) => {
                const isLast = index === messages.length - 1;
                const isUser = message.role === "user";
                return (
                  <List.Item
                    ref={isLast ? lastMessageRef : null}
                    style={{
                      border: "none",
                      padding: "8px 0",
                      justifyContent: isUser ? "flex-end" : "flex-start",
                    }}
                  >
                    <div
                      style={{
                        maxWidth: "80%",
                        padding: "8px 12px",
                        borderRadius: "12px",
                        backgroundColor: isUser ? "#1890ff" : "#f5f5f5",
                        color: isUser ? "white" : "black",
                      }}
                    >
                      {isUser ? (
                        <Text style={{ color: "white" }}>
                          {message.content}
                        </Text>
                      ) : (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={mdComponents}
                        >
                          {message.content}
                        </ReactMarkdown>
                      )}
                    </div>
                  </List.Item>
                );
              }}
            />
          )}
          {isSending && <Spin size="small" />}
        </div>

        {/* input */}
        <div style={{ padding: "16px" }}>
          <Space.Compact style={{ width: "100%" }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              autoSize={{ minRows: 1, maxRows: 3 }}
            />
            <Button
              icon={<SendOutlined />}
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isSending}
            />
          </Space.Compact>
        </div>
      </div>
    </div>
  );
}

export default Chatbot;
