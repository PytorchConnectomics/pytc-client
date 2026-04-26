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
  EditOutlined,
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
  updateConversationTitle,
} from "../api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import WorkflowTimeline from "./WorkflowTimeline";
import { useWorkflow } from "../contexts/WorkflowContext";
import AgentProposalCard from "./chat/AgentProposalCard";
import AssistantActionCard from "./chat/AssistantActionCard";
import AssistantCommandCard from "./chat/AssistantCommandCard";
import WorkflowEvidencePanel from "./workflow/WorkflowEvidencePanel";
import { logClientEvent } from "../logging/appEventLog";

const { TextArea } = Input;
const { Text } = Typography;
const MONO_FONT =
  "'SFMono-Regular', Menlo, Monaco, Consolas, 'Liberation Mono', monospace";

const GREETING = {
  role: "assistant",
  content:
    "Tell me the workflow job. I can run the model, start proofreading, use edits for training, compare results, or move screens.",
};

const WORKFLOW_SLASH_COMMANDS = {
  "/status": "status",
  "/next": "next step",
  "/help": "what can the agent do",
  "/infer": "run model",
  "/inference": "run model",
  "/segment": "run model to segment this volume",
  "/proofread": "proofread this data",
  "/train": "start training",
  "/compare": "compare results and compute metrics",
  "/metrics": "compare results and compute metrics",
  "/export": "export evidence bundle",
};

const normalizeWorkflowAgentQuery = (query) => {
  const trimmed = query.trim();
  if (!trimmed.startsWith("/")) {
    return { agentQuery: query, commandAlias: null };
  }
  const [command, ...rest] = trimmed.split(/\s+/);
  const alias = WORKFLOW_SLASH_COMMANDS[command.toLowerCase()];
  if (!alias) {
    return { agentQuery: query, commandAlias: null };
  }
  const suffix = rest.join(" ").trim();
  return {
    agentQuery: suffix ? `${alias}: ${suffix}` : alias,
    commandAlias: command.toLowerCase(),
  };
};

/* ─── helper: truncate a string to `n` chars ─────────────────────────────── */
const truncate = (str, n = 50) =>
  str.length > n ? str.slice(0, n).trimEnd() + "…" : str;

const PROMPT_LEAK_MARKERS = [
  "you are the supervisor agent",
  "response style for biologists",
  "routing — decide",
  "routing - decide",
  "critical rules:",
  "sub-agents:",
  "search_documentation",
  "delegate_to_training_agent",
  "delegate_to_inference_agent",
];

const sanitizeLoadedMessage = (message) => {
  if (message.role !== "assistant") return message;
  const content = String(message.content || "");
  const lower = content.toLowerCase();
  const leaked = PROMPT_LEAK_MARKERS.some((marker) => lower.includes(marker));
  if (!leaked) return message;
  return {
    ...message,
    content:
      "Hi. I can help run this segmentation loop. Ask me to run the model, proofread masks, use saved edits for training, or compare results.",
  };
};

/* ═══════════════════════════════════════════════════════════════════════════ */

function Chatbot({
  onClose,
  forceShowWorkflowInspector = false,
  onWorkflowInspectorConsumed,
}) {
  /* ── state ─────────────────────────────────────────────────────────────── */
  const [conversations, setConversations] = useState([]);
  const [activeConvoId, setActiveConvoId] = useState(null);
  const [messages, setMessages] = useState([GREETING]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isLoadingConvo, setIsLoadingConvo] = useState(false);
  const [showWorkflowInspector, setShowWorkflowInspector] = useState(false);
  const [showWorkflowTimeline, setShowWorkflowTimeline] = useState(false);
  const [editingTitleId, setEditingTitleId] = useState(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [isRenamingTitle, setIsRenamingTitle] = useState(false);

  const lastMessageRef = useRef(null);
  const workflowContext = useWorkflow();
  const runClientEffects = workflowContext?.runClientEffects;
  const executeAssistantItem = workflowContext?.executeAssistantItem;
  const workflow = workflowContext?.workflow;

  const shouldUseWorkflowAgent = () => {
    if (!workflowContext?.workflow?.id || !workflowContext?.queryAgent) {
      return false;
    }
    return true;
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

  useEffect(() => {
    if (!forceShowWorkflowInspector) return;
    setShowWorkflowInspector(true);
    onWorkflowInspectorConsumed?.();
  }, [forceShowWorkflowInspector, onWorkflowInspectorConsumed]);

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
        convo.messages
          ?.map((m) => ({
            role: m.role,
            content: m.content,
            source: m.source,
            actions: m.actions || [],
            commands: m.commands || [],
            proposals: m.proposals || [],
          }))
          .map(sanitizeLoadedMessage) ??
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
    const isGreeting =
      /^(hi|hello|hey|yo|sup|hiya)[\s!.?,]*$/i.test(query.trim());
    setInputValue("");
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setIsSending(true);
    try {
      if (shouldUseWorkflowAgent(query)) {
        const { agentQuery, commandAlias } = normalizeWorkflowAgentQuery(query);
        logClientEvent("workflow_agent_chat_sent", {
          source: "chatbot",
          message: "Workflow-agent chat query sent",
          data: {
            workflowId: workflowContext.workflow.id,
            conversationId: activeConvoId,
            queryPreview: query.slice(0, 160),
            agentQueryPreview: agentQuery.slice(0, 160),
            commandAlias,
            queryLength: query.length,
          },
        });
        const data = await workflowContext.queryAgent(agentQuery, activeConvoId);
        const response =
          data?.response ||
          "I could not inspect the workflow state for that request.";
        const returnedConvoId =
          data?.conversationId ?? data?.conversation_id ?? activeConvoId;
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: response,
            source: data?.source || "workflow_orchestrator",
            actions: isGreeting ? [] : data?.actions || [],
            commands: isGreeting ? [] : data?.commands || [],
            proposals: isGreeting ? [] : data?.proposals || [],
          },
        ]);
        if (!activeConvoId && returnedConvoId) {
          setActiveConvoId(returnedConvoId);
        }
        const convos = await listConversations();
        if (convos) setConversations(convos);
        logClientEvent("workflow_agent_chat_completed", {
          source: "chatbot",
          message: "Workflow-agent chat query completed",
          data: {
            workflowId: workflowContext.workflow.id,
            conversationId: returnedConvoId,
            responseSource: data?.source || "workflow_orchestrator",
            intent: data?.intent || null,
            commandAlias,
            actionCount: data?.actions?.length || 0,
            commandCount: data?.commands?.length || 0,
            proposalCount: data?.proposals?.length || 0,
          },
        });
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
      logClientEvent("chat_send_failed", {
        level: "ERROR",
        source: "chatbot",
        message: e.message || "Error contacting chatbot.",
        data: {
          workflowId: workflowContext?.workflow?.id || null,
          activeConvoId,
          queryPreview: query.slice(0, 160),
        },
      });
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

  const startRenameConvo = (conversation, e) => {
    e?.stopPropagation();
    setEditingTitleId(conversation.id);
    setDraftTitle(conversation.title || "New Chat");
  };

  const cancelRenameConvo = (e) => {
    e?.stopPropagation();
    setEditingTitleId(null);
    setDraftTitle("");
  };

  const submitRenameConvo = async (conversation, e) => {
    e?.stopPropagation();
    const nextTitle = draftTitle.trim();
    if (!nextTitle || nextTitle === conversation.title || isRenamingTitle) {
      cancelRenameConvo(e);
      return;
    }
    setIsRenamingTitle(true);
    try {
      const updated = await updateConversationTitle(conversation.id, nextTitle);
      setConversations((prev) =>
        prev.map((item) =>
          item.id === conversation.id ? { ...item, ...updated } : item,
        ),
      );
      logClientEvent("chat_conversation_renamed", {
        source: "chatbot",
        message: "Chat conversation renamed",
        data: {
          conversationId: conversation.id,
          titleLength: nextTitle.length,
        },
      });
    } catch (error) {
      logClientEvent("chat_conversation_rename_failed", {
        level: "ERROR",
        source: "chatbot",
        message: error.message || "Chat conversation rename failed",
        data: { conversationId: conversation.id },
      });
    } finally {
      setIsRenamingTitle(false);
      setEditingTitleId(null);
      setDraftTitle("");
    }
  };

  const handleRunAssistantItem = async (item) => {
    const itemId = item?.id || item?.title || item?.label || "assistant-item";
    logClientEvent("assistant_item_run_started", {
      source: "chatbot",
      message: "Assistant in-app item run started",
      data: {
        workflowId: workflow?.id || null,
        activeConvoId,
        itemId,
        itemLabel: item?.title || item?.label || null,
        itemType: item?.command ? "command" : "action",
        runtimeActionKind: item?.client_effects?.runtime_action?.kind || null,
      },
    });
    try {
      if (executeAssistantItem) {
        await executeAssistantItem(item);
        logClientEvent("assistant_item_run_completed", {
          source: "chatbot",
          message: "Assistant in-app item run completed",
          data: { workflowId: workflow?.id || null, activeConvoId, itemId },
        });
        return;
      }
      if (!item?.client_effects || !runClientEffects) return;
      await runClientEffects(item.client_effects);
      logClientEvent("assistant_item_run_completed", {
        source: "chatbot",
        message: "Assistant in-app item run completed",
        data: { workflowId: workflow?.id || null, activeConvoId, itemId },
      });
    } catch (error) {
      logClientEvent("assistant_item_run_failed", {
        level: "ERROR",
        source: "chatbot",
        message: error.message || "Assistant in-app item run failed",
        data: { workflowId: workflow?.id || null, activeConvoId, itemId },
      });
      throw error;
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
    <div
      style={{
        height: "100vh",
        display: "flex",
        background: "#f3f4f1",
      }}
    >
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      {sidebarOpen && (
        <div
          style={{
            width: 216,
            minWidth: 216,
            borderRight: "1px solid #e5e7eb",
            display: "flex",
            flexDirection: "column",
            background: "#fbfbfa",
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
                  aria-label="New chat"
                />
              </Tooltip>
              <Tooltip title="Collapse sidebar">
                <Button
                  type="text"
                  size="small"
                  icon={<MenuFoldOutlined />}
                  onClick={() => setSidebarOpen(false)}
                  aria-label="Collapse conversations"
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
                  borderRadius: 8,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background: c.id === activeConvoId ? "#f3f4f6" : "transparent",
                  border:
                    c.id === activeConvoId
                      ? "1px solid #d1d5db"
                      : "1px solid transparent",
                  transition: "background 0.15s ease, border-color 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  if (c.id !== activeConvoId)
                    e.currentTarget.style.background = "#f5f5f5";
                }}
                onMouseLeave={(e) => {
                  if (c.id !== activeConvoId)
                    e.currentTarget.style.background = "transparent";
                }}
              >
                <MessageOutlined
                  style={{ fontSize: 13, color: "#999", flexShrink: 0 }}
                />
                {editingTitleId === c.id ? (
                  <Input
                    size="small"
                    value={draftTitle}
                    autoFocus
                    disabled={isRenamingTitle}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    onPressEnter={(e) => submitRenameConvo(c, e)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") cancelRenameConvo(e);
                    }}
                    onBlur={(e) => submitRenameConvo(c, e)}
                    aria-label={`Rename chat ${c.title}`}
                    style={{ flex: 1, minWidth: 0 }}
                  />
                ) : (
                  <Text
                    ellipsis
                    onDoubleClick={(e) => startRenameConvo(c, e)}
                    style={{ flex: 1, fontSize: 13, lineHeight: "18px" }}
                    title="Double-click to rename"
                  >
                    {truncate(c.title)}
                  </Text>
                )}
                {editingTitleId !== c.id && (
                  <Tooltip title="Rename">
                    <Button
                      type="text"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={(e) => startRenameConvo(c, e)}
                      aria-label={`Rename chat ${c.title}`}
                      style={{
                        flexShrink: 0,
                        opacity: 0.35,
                        transition: "opacity 0.15s",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.opacity = "1")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.opacity = "0.35")
                      }
                    />
                  </Tooltip>
                )}
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
                    aria-label={`Delete chat ${c.title}`}
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
            padding: "12px 14px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid #e5e7eb",
            background: "#fafaf9",
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
                  aria-label="Show conversations"
                />
              </Tooltip>
            )}
            <div>
              <Text
                strong
                style={{
                  color: "#111827",
                  display: "block",
                  fontFamily: MONO_FONT,
                  letterSpacing: "0.02em",
                }}
              >
                Assistant
              </Text>
            </div>
          </Space>
          <Space>
            {workflow?.id && (
              <Button
                type="text"
                size="small"
                onClick={() =>
                  setShowWorkflowInspector((current) => !current)
                }
              >
                {showWorkflowInspector ? "Hide Status" : "Status"}
              </Button>
            )}
            <Tooltip title="New chat">
              <Button
                type="text"
                icon={<PlusOutlined />}
                onClick={handleNewChat}
                size="small"
                aria-label="New chat"
              />
            </Tooltip>
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={onClose}
              size="small"
              aria-label="Close assistant"
            />
          </Space>
        </div>

        {showWorkflowInspector && (
          <div style={{ borderBottom: "1px solid #ececec" }}>
            <WorkflowEvidencePanel compact />
            <div
              style={{
                padding: "0 12px 10px",
                background: "#fffdfa",
              }}
            >
              <Button
                size="small"
                type="text"
                onClick={() => setShowWorkflowTimeline((current) => !current)}
              >
                {showWorkflowTimeline ? "Hide timeline" : "Show timeline"}
              </Button>
            </div>
            {showWorkflowTimeline && (
              <WorkflowTimeline limit={5} showFilters={false} />
            )}
          </div>
        )}

        {/* messages */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: "14px",
            background: "#f6f5f2",
          }}
        >
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
                      padding: "10px 0",
                      justifyContent: isUser ? "flex-end" : "flex-start",
                    }}
                  >
                    <div
                      style={{
                        width: isUser ? "auto" : "min(100%, 760px)",
                        maxWidth: isUser ? "78%" : "88%",
                        padding: isUser ? "10px 12px" : "12px",
                        borderRadius: isUser ? "14px 14px 4px 14px" : "14px",
                        background: isUser ? "#1d4ed8" : "#ffffff",
                        color: isUser ? "white" : "black",
                        border: isUser ? "none" : "1px solid #e5e7eb",
                        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05)",
                      }}
                    >
                      {isUser ? (
                        <Text style={{ color: "white" }}>
                          {message.content}
                        </Text>
                      ) : (
                        <Space
                          direction="vertical"
                          size={10}
                          style={{ width: "100%" }}
                        >
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={mdComponents}
                          >
                            {message.content}
                          </ReactMarkdown>
                          {(message.actions?.length > 0 ||
                            message.commands?.length > 0 ||
                            message.proposals?.length > 0) && (
                            <div
                              style={{
                                display: "grid",
                                gap: 10,
                                marginTop: 2,
                              }}
                            >
                              {message.actions?.map((action) => (
                                <AssistantActionCard
                                  key={action.id}
                                  action={action}
                                  onRun={handleRunAssistantItem}
                                />
                              ))}
                              {message.commands?.map((command) => (
                                <AssistantCommandCard
                                  key={command.id}
                                  command={command}
                                  onRun={handleRunAssistantItem}
                                />
                              ))}
                              {message.proposals?.map((proposal) => (
                                <AgentProposalCard
                                  key={proposal.id}
                                  proposal={{
                                    ...(proposal.payload || {}),
                                    id: proposal.id,
                                    type:
                                      proposal.payload?.action || "agent_proposal",
                                    rationale: proposal.summary,
                                    ...(proposal.payload?.params || {}),
                                  }}
                                  onApprove={() =>
                                    workflowContext?.approveAgentAction?.(
                                      proposal.id,
                                    )
                                  }
                                  onReject={() =>
                                    workflowContext?.rejectAgentAction?.(
                                      proposal.id,
                                    )
                                  }
                                />
                              ))}
                            </div>
                          )}
                        </Space>
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
        <div
          style={{
            padding: "12px 14px 14px",
            borderTop: "1px solid #e5e7eb",
            background: "#fafaf9",
          }}
        >
          <Space.Compact style={{ width: "100%" }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Message"
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
