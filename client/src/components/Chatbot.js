import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  Button,
  Input,
  List,
  Typography,
  Space,
  Spin,
  Tag,
  message,
} from "antd";
import { SendOutlined, CloseOutlined } from "@ant-design/icons";
import { getWorkflowAgentConversation, queryChatBot } from "../api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useWorkflow } from "../contexts/WorkflowContext";
import AgentProposalCard from "./chat/AgentProposalCard";
import AssistantActionCard from "./chat/AssistantActionCard";
import AssistantCommandCard from "./chat/AssistantCommandCard";
import AssistantTrace from "./chat/AssistantTrace";
import AgentBadge, { getAgentVisual } from "./chat/AgentVisuals";
import { logClientEvent } from "../logging/appEventLog";

const { TextArea } = Input;
const { Text } = Typography;
const MONO_FONT =
  "'SFMono-Regular', Menlo, Monaco, Consolas, 'Liberation Mono', monospace";

const GREETING = {
  role: "assistant",
  content:
    "I’ll coordinate the workflow and pull in specialist agents for data, visualization, proofreading, training, inference, and evidence when needed. Tell me what you want to do in plain language.",
};

const QUICK_NEXT_QUERY = "What should I do next?";
const CONTINUOUS_CHAT_STORAGE_KEY = "pytc.workflowAssistant.continuousChat.v1";

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

const WORKFLOW_AGENT_KEYWORDS = [
  "workflow",
  "project",
  "dataset",
  "directory",
  "folder",
  "folders",
  "file",
  "files",
  "volume",
  "image",
  "label",
  "mask",
  "segmentation",
  "segment",
  "proofread",
  "proofreading",
  "train",
  "training",
  "retrain",
  "inference",
  "infer",
  "run model",
  "checkpoint",
  "config",
  "visualize",
  "visualise",
  "vis",
  "viz",
  "viewer",
  "scales",
  "voxel",
  "resolution",
  "status",
  "next step",
  "what next",
  "what should i do",
  "what do you need",
  "what can you do",
  "help me",
  "run things",
  "mount",
  "reset workspace",
  "clear workspace",
  "monitor",
  "logs",
  "tensorboard",
  "evaluate",
  "metrics",
  "compare",
  "export",
  "evidence",
];

const WORKFLOW_AGENT_PATTERNS = [
  /\b(view|show|open|inspect|see|vis|viz)\b.{0,48}\b(data|volume|volumes|image|images|label|labels|mask|masks|seg|segs|segmentation|segmentations)\b/,
  /\blook at\b.{0,48}\b(data|volume|volumes|image|images|label|labels|mask|masks|seg|segs|segmentation|segmentations)\b/,
  /\bwhat\b.{0,40}\b(looking at|loaded|open|mounted|project|dataset|volume|data)\b/,
  /\bwhere\b.{0,40}\b(are we|am i|is this|in the workflow)\b/,
  /\b(run|start|launch)\b.{0,48}\b(app|model|inference|training|proofread|proofreading|viewer|visualization)\b/,
];

const WORKFLOW_FOLLOW_UP_PATTERNS = [
  /\b(take a look|look at|show|open|view|inspect|check)\b/,
  /\b(it|this|that|those|them|there|here|first|next|again|same one)\b/,
  /\b(go ahead|do it|do that|run it|start it|use that|sounds good)\b/,
  /^(yes|yeah|yep|ok|okay|sure|please|what|why|how|wait|huh)[\s!.?,]*$/i,
];

const toList = (value) => (Array.isArray(value) ? value : []);

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

const clientEffectsWithoutRuntime = (effects = {}) => {
  if (!effects || typeof effects !== "object") return effects;
  const { runtime_action: _runtimeAction, ...rest } = effects;
  return rest;
};

const runnableAttachmentCount = (message = {}) =>
  (Array.isArray(message.actions) ? message.actions.length : 0) +
  (Array.isArray(message.commands) ? message.commands.length : 0) +
  (Array.isArray(message.proposals) ? message.proposals.length : 0);

const agentIdentityKey = (agent = {}) =>
  agent.agent_type ||
  agent.type ||
  agent.label ||
  agent.agent_label ||
  "project_manager";

const messageAgents = (message = {}) => {
  const agents = [];
  const addAgent = (agent) => {
    if (!agent) return;
    const visual = getAgentVisual(agent);
    const key = agentIdentityKey(agent);
    if (agents.some((item) => item.key === key)) return;
    agents.push({ key, ...visual });
  };

  (message.trace || []).forEach((item) => addAgent(item));
  (message.actions || []).forEach((action) => {
    addAgent(action.specialist_agent || action);
    addAgent(action.orchestrator_agent);
  });
  (message.proposals || []).forEach((proposal) => {
    const payload = proposal.payload || proposal;
    addAgent(payload.specialist_agent || payload.action_card?.specialist_agent);
    addAgent(
      payload.orchestrator_agent || payload.action_card?.orchestrator_agent,
    );
  });

  return agents;
};

const STALE_WORKFLOW_CARD_NOTICE =
  "That run card belonged to an earlier workflow, so I hid the stale button. Ask me to stage it again and I'll make a fresh one for this project.";

const STALE_WORKFLOW_CARD_PATTERN =
  /(review (?:the )?run card|review run|approve|run in app|launch(?:ing| it)?|run card)/i;

const proposalRequestFromEvent = (proposal = {}) => {
  const payload = proposal.payload || {};
  const params = payload.params || proposal.params || {};
  const action = payload.action || proposal.action || proposal.type;
  if (!action || !params || typeof params !== "object") return null;
  return {
    action,
    summary: proposal.summary || `Approve agent proposal: ${action}.`,
    payload: params,
  };
};

const isProposalNotFoundError = (error) => {
  const messageText = String(error?.message || error || "").toLowerCase();
  return (
    messageText.includes("agent proposal not found") ||
    messageText.includes("404")
  );
};

const isGreetingQuery = (query) =>
  /^(hi|hello|hey|yo|sup|hiya)[\s!.?,]*$/i.test(query.trim());

const isGibberishQuery = (query) => {
  const lower = query.trim().toLowerCase();
  const compact = lower.replace(/[^a-z0-9]+/g, "");
  if (!compact || lower.startsWith("/")) return false;
  const vowelCount = (compact.match(/[aeiou]/g) || []).length;
  return compact.length >= 8 && !/\s/.test(lower) && vowelCount <= 2;
};

const isWorkflowAgentQuery = (query) => {
  const trimmed = query.trim();
  if (!trimmed) return false;
  const normalized = normalizeWorkflowAgentQuery(trimmed);
  if (normalized.commandAlias) return true;
  if (isGreetingQuery(trimmed)) return true;
  const lower = trimmed.toLowerCase();
  return (
    WORKFLOW_AGENT_KEYWORDS.some((keyword) => lower.includes(keyword)) ||
    WORKFLOW_AGENT_PATTERNS.some((pattern) => pattern.test(lower))
  );
};

const getLastAssistantMessage = (messages = []) => {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "assistant") {
      return messages[index];
    }
  }
  return null;
};

const isWorkflowFollowUpQuery = (query, messages = [], workflowId = null) => {
  const lastAssistant = getLastAssistantMessage(messages);
  if (lastAssistant?.source !== "workflow_orchestrator") {
    return false;
  }
  if (
    lastAssistant.workflow_id &&
    workflowId &&
    String(lastAssistant.workflow_id) !== String(workflowId)
  ) {
    return false;
  }
  const trimmed = query.trim();
  if (!trimmed || trimmed.length > 140) {
    return false;
  }
  const lower = trimmed.toLowerCase();
  return WORKFLOW_FOLLOW_UP_PATTERNS.some((pattern) => pattern.test(lower));
};

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

const parseToolCallJson = (text) => {
  try {
    const parsed = JSON.parse(text);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      typeof parsed.name !== "string"
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

const parseRawToolCall = (content) => {
  const text = String(content || "").trim();
  if (text.startsWith("{") && text.endsWith("}")) {
    const parsed = parseToolCallJson(text);
    if (parsed) return parsed;
  }
  const embeddedJson = text.match(/\{[\s\S]*"name"\s*:\s*"[^"]+"[\s\S]*\}/);
  return embeddedJson ? parseToolCallJson(embeddedJson[0]) : null;
};

const normalizeAssistantContent = (content) => {
  const toolCall = parseRawToolCall(content);
  if (!toolCall) return String(content || "");
  if (toolCall.name === "visualize_volume_pair") {
    return (
      "I should not have shown that internal command.\n" +
      "Do this: use the workflow action card to choose a volume pair, then open it in Visualize."
    );
  }
  return (
    "I should not have shown that internal command.\n" +
    "Tell me what you want to do in plain language and I will offer a safe app action."
  );
};

const sanitizeLoadedMessage = (message, currentWorkflowId = null) => {
  if (message.role !== "assistant") return message;
  const content = String(message.content || "");
  const normalizedContent = normalizeAssistantContent(content);
  const messageWorkflowId = Number(
    message.workflow_id || message.workflowId || 0,
  );
  const activeWorkflowId = Number(currentWorkflowId || 0);
  if (
    messageWorkflowId &&
    activeWorkflowId &&
    messageWorkflowId !== activeWorkflowId
  ) {
    const shouldExplainStrippedCard =
      runnableAttachmentCount(message) > 0 &&
      STALE_WORKFLOW_CARD_PATTERN.test(normalizedContent) &&
      !normalizedContent.includes(STALE_WORKFLOW_CARD_NOTICE);
    return {
      ...message,
      content: shouldExplainStrippedCard
        ? `${normalizedContent}\n\n${STALE_WORKFLOW_CARD_NOTICE}`
        : normalizedContent,
      actions: [],
      commands: [],
      proposals: [],
      trace: [],
    };
  }
  if (normalizedContent !== content) {
    return { ...message, content: normalizedContent };
  }
  const lower = content.toLowerCase();
  const leaked = PROMPT_LEAK_MARKERS.some((marker) => lower.includes(marker));
  if (!leaked) return message;
  return {
    ...message,
    content:
      "Hi. I can help run this segmentation loop. Ask me to run the model, proofread masks, use saved edits for training, or compare results.",
  };
};

const loadContinuousChatState = (currentWorkflowId = null) => {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return { activeConvoId: null, messages: [GREETING] };
  }
  try {
    const raw = window.sessionStorage.getItem(CONTINUOUS_CHAT_STORAGE_KEY);
    if (!raw) return { activeConvoId: null, messages: [GREETING] };
    const parsed = JSON.parse(raw);
    const storedMessages = Array.isArray(parsed?.messages)
      ? parsed.messages
          .filter(
            (message) =>
              message &&
              (message.role === "assistant" || message.role === "user") &&
              typeof message.content === "string",
          )
          .map((message) => sanitizeLoadedMessage(message, currentWorkflowId))
      : [];
    return {
      activeConvoId: parsed?.activeConvoId || parsed?.conversationId || null,
      messages: storedMessages.length ? storedMessages : [GREETING],
    };
  } catch {
    return { activeConvoId: null, messages: [GREETING] };
  }
};

const saveContinuousChatState = ({ activeConvoId, messages }) => {
  if (typeof window === "undefined" || !window.sessionStorage) return;
  try {
    window.sessionStorage.setItem(
      CONTINUOUS_CHAT_STORAGE_KEY,
      JSON.stringify({ activeConvoId, messages }),
    );
  } catch {
    // Session persistence is a convenience; chat should still work without it.
  }
};

const workflowConversationMessageToChatMessage = (
  message,
  currentWorkflowId = null,
) =>
  sanitizeLoadedMessage(
    {
      role: message.role,
      content: message.content,
      source: message.source || undefined,
      workflow_id: message.workflow_id || currentWorkflowId || undefined,
      actions: message.actions || [],
      commands: message.commands || [],
      proposals: message.proposals || [],
      trace: message.trace || [],
    },
    currentWorkflowId,
  );

const byProposalId = (messages = []) => {
  const index = {};
  messages.forEach((message) => {
    (message?.proposals || []).forEach((proposal) => {
      if (proposal?.id == null) return;
      index[String(proposal.id)] = {
        ...(proposal?.payload ? { payload: proposal.payload } : {}),
        ...proposal,
      };
    });
  });
  return index;
};

const reconcileProposal = (localProposal, hydratedProposal) => {
  if (!localProposal?.id || !hydratedProposal) return localProposal;
  const approval_status =
    hydratedProposal.approval_status ||
    localProposal.approval_status ||
    "pending";
  return {
    ...localProposal,
    ...hydratedProposal,
    summary: hydratedProposal.summary || localProposal.summary,
    payload: {
      ...(localProposal?.payload || {}),
      ...(hydratedProposal.payload || {}),
    },
    params: {
      ...(localProposal?.params || {}),
      ...(hydratedProposal.params || {}),
    },
    approval_status,
  };
};

const reconcileProposalStatuses = (messages = [], hydratedMessages = []) => {
  const hydrated = byProposalId(hydratedMessages);
  return messages.map((message) => {
    if (
      !message ||
      !Array.isArray(message.proposals) ||
      !message.proposals.length
    ) {
      return message;
    }
    return {
      ...message,
      proposals: message.proposals.map((proposal) => {
        const hydratedProposal = hydrated[String(proposal?.id)];
        if (!hydratedProposal) return proposal;
        return reconcileProposal(proposal, hydratedProposal);
      }),
    };
  });
};

/* ═══════════════════════════════════════════════════════════════════════════ */

function Chatbot({
  onClose,
  queuedWorkflowQuery = null,
  onQueuedWorkflowQueryConsumed,
}) {
  /* ── state ─────────────────────────────────────────────────────────────── */
  const workflowContext = useWorkflow();
  const runClientEffects = workflowContext?.runClientEffects;
  const executeAssistantItem = workflowContext?.executeAssistantItem;
  const workflow = workflowContext?.workflow;
  const initialChatStateRef = useRef(null);
  if (initialChatStateRef.current === null) {
    initialChatStateRef.current = loadContinuousChatState(workflow?.id);
  }

  const [activeConvoId, setActiveConvoId] = useState(
    initialChatStateRef.current.activeConvoId,
  );
  const [messages, setMessages] = useState(
    initialChatStateRef.current.messages,
  );
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);

  const lastMessageRef = useRef(null);
  const handledQueuedQueryRef = useRef(null);
  const hydratedWorkflowConversationRef = useRef(null);

  const appendLocalProposalToLatestAssistant = useCallback((proposal) => {
    if (!proposal?.id) return;
    setMessages((prev) => {
      const next = [...prev];
      for (let index = next.length - 1; index >= 0; index -= 1) {
        if (next[index]?.role !== "assistant") continue;
        const proposals = next[index].proposals || [];
        next[index] = {
          ...next[index],
          proposals: [...proposals, proposal],
        };
        return next;
      }
      return prev;
    });
  }, []);

  const updateLocalProposalStatus = useCallback(
    (proposalId, approvalStatus) => {
      if (!proposalId) return;
      setMessages((prev) =>
        prev.map((entry) => {
          if (!Array.isArray(entry.proposals) || entry.proposals.length === 0) {
            return entry;
          }
          return {
            ...entry,
            proposals: entry.proposals.map((proposal) =>
              proposal.id === proposalId
                ? { ...proposal, approval_status: approvalStatus }
                : proposal,
            ),
          };
        }),
      );
    },
    [],
  );

  const buildTrainingRunProposal = useCallback((item) => {
    const effects = item?.client_effects || {};
    const runtimeAction = effects.runtime_action || {};
    const configPreset = effects.set_training_config_preset || "";
    const imagePath = effects.set_training_image_path || "";
    const labelPath = effects.set_training_label_path || "";
    const outputPath = effects.set_training_output_path || "";
    const parameterMode = runtimeAction.parameter_mode || "agent_default";

    return {
      action: "start_training_run",
      summary: `Approve training run: ${item?.title || item?.label || "start training"}.`,
      payload: {
        client_effects: effects,
        action_card: item?.action_card || null,
        orchestrator_agent: item?.orchestrator_agent || null,
        specialist_agent: item?.specialist_agent || null,
        config_preset: configPreset,
        image_path: imagePath,
        label_path: labelPath,
        output_path: outputPath,
        parameter_mode: parameterMode,
        autopick_parameters: Boolean(runtimeAction.autopick_parameters),
        training_volume_subset: effects.training_volume_subset || null,
      },
    };
  }, []);

  const buildClientEffectsProposal = useCallback((item) => {
    const effects = item?.client_effects || {};
    const label = item?.title || item?.label || item?.id || "assistant action";
    return {
      action: "run_client_effects",
      summary: `Approve app action: ${label}.`,
      payload: {
        client_effects: effects,
        action_card: item?.action_card || null,
        orchestrator_agent: item?.orchestrator_agent || null,
        specialist_agent: item?.specialist_agent || null,
        item_id: item?.id || null,
        item_label: label,
        item_type: item?.command ? "command" : "action",
        risk_level: item?.risk_level || null,
        runtime_action: effects.runtime_action || null,
        workflow_action: effects.workflow_action || null,
      },
    };
  }, []);

  const populateTrainingReviewForm = useCallback(
    async (item, itemId) => {
      if (!runClientEffects) return true;
      const reviewEffects = clientEffectsWithoutRuntime(item?.client_effects);
      try {
        await runClientEffects(reviewEffects);
        logClientEvent("assistant_item_training_review_populated", {
          source: "chatbot",
          message: "Assistant populated the training review form",
          data: {
            workflowId: workflow?.id || null,
            activeConvoId,
            itemId,
          },
        });
        return true;
      } catch (error) {
        const fallbackEffects = {
          navigate_to: reviewEffects?.navigate_to || "training",
          set_training_image_path: reviewEffects?.set_training_image_path,
          set_training_label_path: reviewEffects?.set_training_label_path,
          set_training_output_path: reviewEffects?.set_training_output_path,
          set_training_log_path: reviewEffects?.set_training_log_path,
          refresh_project_progress: reviewEffects?.refresh_project_progress,
        };
        try {
          await runClientEffects(fallbackEffects);
          logClientEvent("assistant_item_training_review_partial", {
            level: "WARN",
            source: "chatbot",
            message:
              error.message ||
              "Training review form populated without every requested effect",
            data: {
              workflowId: workflow?.id || null,
              activeConvoId,
              itemId,
            },
          });
          message.warning(
            "I filled the run paths, but one review detail needs attention before launch.",
          );
          return false;
        } catch (fallbackError) {
          logClientEvent("assistant_item_training_review_failed", {
            level: "ERROR",
            source: "chatbot",
            message:
              fallbackError.message ||
              error.message ||
              "Could not populate the training review form",
            data: {
              workflowId: workflow?.id || null,
              activeConvoId,
              itemId,
            },
          });
          throw error;
        }
      }
    },
    [activeConvoId, runClientEffects, workflow?.id],
  );

  const shouldUseWorkflowAgent = (query) => {
    if (!workflowContext?.workflow?.id || !workflowContext?.queryAgent) {
      return false;
    }
    if (isGibberishQuery(query)) {
      return false;
    }
    return (
      isWorkflowAgentQuery(query) ||
      isWorkflowFollowUpQuery(query, messages, workflowContext.workflow.id)
    );
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
    saveContinuousChatState({ activeConvoId, messages });
  }, [activeConvoId, messages]);

  useEffect(() => {
    if (!workflow?.id) return;
    setMessages((prev) =>
      prev.map((message) => sanitizeLoadedMessage(message, workflow.id)),
    );
  }, [workflow?.id]);

  useEffect(() => {
    if (!workflow?.id) return;
    if (hydratedWorkflowConversationRef.current === workflow.id) return;
    hydratedWorkflowConversationRef.current = workflow.id;

    let cancelled = false;
    getWorkflowAgentConversation(workflow.id)
      .then((conversation) => {
        if (cancelled || !conversation?.messages?.length) return;
        const serverMessages = conversation.messages
          .filter(
            (message) =>
              message &&
              (message.role === "assistant" || message.role === "user") &&
              typeof message.content === "string",
          )
          .map((message) =>
            workflowConversationMessageToChatMessage(message, workflow.id),
          );
        if (!serverMessages.length) return;
        setActiveConvoId(
          (current) =>
            current ||
            conversation.conversation_id ||
            conversation.conversationId ||
            null,
        );
        setMessages((previousMessages) => {
          const hasLocalUserMessages = previousMessages.some(
            (message) => message.role === "user",
          );
          if (hasLocalUserMessages) {
            return reconcileProposalStatuses(previousMessages, serverMessages);
          }
          return reconcileProposalStatuses(serverMessages, serverMessages);
        });
      })
      .catch((error) => {
        logClientEvent("workflow_agent_chat_hydration_failed", {
          level: "WARNING",
          source: "chatbot",
          message: error.message || "Could not hydrate workflow chat history.",
          data: { workflowId: workflow.id },
        });
      });
    return () => {
      cancelled = true;
    };
  }, [workflow?.id]);

  const sendWorkflowAgentMessage = useCallback(
    async (
      query,
      {
        displayQuery = query,
        source = "chatbot",
        hideGreetingActions = true,
      } = {},
    ) => {
      if (!query.trim() || isSending) return false;
      if (!workflowContext?.workflow?.id || !workflowContext?.queryAgent) {
        return false;
      }

      const isGreeting = hideGreetingActions && isGreetingQuery(displayQuery);
      const { agentQuery, commandAlias } = normalizeWorkflowAgentQuery(query);
      setMessages((prev) => [...prev, { role: "user", content: displayQuery }]);
      setIsSending(true);
      try {
        logClientEvent("workflow_agent_chat_sent", {
          source,
          message: "Workflow-agent chat query sent",
          data: {
            workflowId: workflowContext.workflow.id,
            conversationId: activeConvoId,
            queryPreview: displayQuery.slice(0, 160),
            agentQueryPreview: agentQuery.slice(0, 160),
            commandAlias,
            queryLength: agentQuery.length,
          },
        });
        const data = await workflowContext.queryAgent(
          agentQuery,
          activeConvoId,
        );
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
            workflow_id: workflowContext.workflow.id,
            actions: isGreeting ? [] : data?.actions || [],
            commands: isGreeting ? [] : data?.commands || [],
            proposals: isGreeting ? [] : data?.proposals || [],
            trace: isGreeting ? [] : data?.trace || [],
          },
        ]);
        if (!activeConvoId && returnedConvoId) {
          setActiveConvoId(returnedConvoId);
        }
        logClientEvent("workflow_agent_chat_completed", {
          source,
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
            traceCount: data?.trace?.length || 0,
          },
        });
        return true;
      } catch (e) {
        logClientEvent("chat_send_failed", {
          level: "ERROR",
          source,
          message: e.message || "Error contacting chatbot.",
          data: {
            workflowId: workflowContext?.workflow?.id || null,
            activeConvoId,
            queryPreview: displayQuery.slice(0, 160),
          },
        });
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: e.message || "Error contacting chatbot.",
          },
        ]);
        return false;
      } finally {
        setIsSending(false);
      }
    },
    [activeConvoId, isSending, workflowContext],
  );

  useEffect(() => {
    if (!queuedWorkflowQuery?.id) return;
    if (handledQueuedQueryRef.current === queuedWorkflowQuery.id) return;
    if (isSending) return;

    handledQueuedQueryRef.current = queuedWorkflowQuery.id;
    onQueuedWorkflowQueryConsumed?.(queuedWorkflowQuery.id);
    sendWorkflowAgentMessage(queuedWorkflowQuery.query || QUICK_NEXT_QUERY, {
      displayQuery: queuedWorkflowQuery.displayText || QUICK_NEXT_QUERY,
      source: queuedWorkflowQuery.source || "quick_next",
      hideGreetingActions: false,
    });
  }, [
    isSending,
    onQueuedWorkflowQueryConsumed,
    queuedWorkflowQuery,
    sendWorkflowAgentMessage,
  ]);

  /* ── send message ──────────────────────────────────────────────────────── */
  const handleSendMessage = async () => {
    if (!inputValue.trim() || isSending) return;
    const query = inputValue;
    setInputValue("");
    try {
      if (shouldUseWorkflowAgent(query)) {
        await sendWorkflowAgentMessage(query);
        return;
      }

      setMessages((prev) => [...prev, { role: "user", content: query }]);
      setIsSending(true);
      logClientEvent("llm_chat_sent", {
        source: "chatbot",
        message: "General assistant chat query sent",
        data: {
          workflowId: workflowContext?.workflow?.id || null,
          conversationId: activeConvoId,
          queryPreview: query.slice(0, 160),
          queryLength: query.length,
        },
      });
      const data = await queryChatBot(query, activeConvoId);
      const response = normalizeAssistantContent(
        data?.response || "Sorry, I could not generate a response.",
      );
      const returnedConvoId = data?.conversationId ?? activeConvoId;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response },
      ]);

      // If this was the first message in a brand-new chat, we now have a convoId
      if (!activeConvoId && returnedConvoId) {
        setActiveConvoId(returnedConvoId);
      }

      logClientEvent("llm_chat_completed", {
        source: "chatbot",
        message: "General assistant chat query completed",
        data: {
          workflowId: workflowContext?.workflow?.id || null,
          conversationId: returnedConvoId,
          responseLength: response.length,
        },
      });
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
      const runtimeKind = item?.client_effects?.runtime_action?.kind;
      if (item?.requires_approval && workflowContext?.proposeAgentAction) {
        const trainingFormReady =
          runtimeKind === "start_training"
            ? await populateTrainingReviewForm(item, itemId)
            : true;
        const proposal =
          runtimeKind === "start_training"
            ? await workflowContext.proposeAgentAction(
                buildTrainingRunProposal(item),
              )
            : await workflowContext.proposeAgentAction(
                buildClientEffectsProposal(item),
              );
        appendLocalProposalToLatestAssistant(proposal);
        message.info(
          runtimeKind === "start_training"
            ? trainingFormReady
              ? "I filled the training form. Review the run, then approve it to start."
              : "I filled the training paths. Check the warning, then approve when it looks right."
            : "Review the proposed app action, then approve it to run.",
        );
        logClientEvent("assistant_item_training_proposal_created", {
          source: "chatbot",
          message: "Assistant created approval-gated app proposal",
          data: {
            workflowId: workflow?.id || null,
            activeConvoId,
            itemId,
            runtimeKind,
            riskLevel: item?.risk_level || null,
          },
        });
        return;
      }
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

  const recreateProposalForCurrentWorkflow = useCallback(
    async (proposal) => {
      const request = proposalRequestFromEvent(proposal);
      if (!request || !workflowContext?.proposeAgentAction) {
        throw new Error("This proposal is stale and cannot be recreated.");
      }
      const nextProposal = await workflowContext.proposeAgentAction(request);
      appendLocalProposalToLatestAssistant(nextProposal);
      return nextProposal;
    },
    [appendLocalProposalToLatestAssistant, workflowContext],
  );

  const handleApproveProposal = useCallback(
    async (proposal, overrides = {}) => {
      if (!proposal?.id || !workflowContext?.approveAgentAction) return;
      const activeWorkflowId = Number(workflowContext?.workflow?.id || 0);
      const proposalWorkflowId = Number(
        proposal.workflow_id || proposal.workflowId || 0,
      );
      const isStaleWorkflowProposal =
        activeWorkflowId &&
        proposalWorkflowId &&
        activeWorkflowId !== proposalWorkflowId;
      let approvalId = proposal.id;
      let recreated = false;
      const approvalOverrides =
        overrides && Object.keys(overrides).length > 0 ? overrides : undefined;

      try {
        if (isStaleWorkflowProposal) {
          const nextProposal =
            await recreateProposalForCurrentWorkflow(proposal);
          approvalId = nextProposal.id;
          recreated = true;
        }
        if (approvalOverrides) {
          await workflowContext.approveAgentAction(
            approvalId,
            approvalOverrides,
          );
        } else {
          await workflowContext.approveAgentAction(approvalId);
        }
        updateLocalProposalStatus(approvalId, "approved");
        if (recreated) {
          updateLocalProposalStatus(proposal.id, "superseded");
        }
      } catch (error) {
        if (!recreated && isProposalNotFoundError(error)) {
          try {
            const nextProposal =
              await recreateProposalForCurrentWorkflow(proposal);
            if (approvalOverrides) {
              await workflowContext.approveAgentAction(
                nextProposal.id,
                approvalOverrides,
              );
            } else {
              await workflowContext.approveAgentAction(nextProposal.id);
            }
            updateLocalProposalStatus(nextProposal.id, "approved");
            updateLocalProposalStatus(proposal.id, "superseded");
            message.info(
              "That run card was stale, so I recreated it and approved the fresh one.",
            );
            return;
          } catch (retryError) {
            logClientEvent("assistant_proposal_recreate_failed", {
              level: "ERROR",
              source: "chatbot",
              message:
                retryError.message || "Failed to recreate stale proposal.",
              data: {
                workflowId: activeWorkflowId || null,
                proposalId: proposal.id,
                proposalWorkflowId: proposalWorkflowId || null,
              },
            });
            message.error(
              retryError.message || "Could not approve that proposal.",
            );
            return;
          }
        }
        logClientEvent("assistant_proposal_approval_failed", {
          level: "ERROR",
          source: "chatbot",
          message: error.message || "Failed to approve proposal.",
          data: {
            workflowId: activeWorkflowId || null,
            proposalId: proposal.id,
            proposalWorkflowId: proposalWorkflowId || null,
          },
        });
        message.error(error.message || "Could not approve that proposal.");
      }
    },
    [
      recreateProposalForCurrentWorkflow,
      updateLocalProposalStatus,
      workflowContext,
    ],
  );

  const handleRejectProposal = useCallback(
    async (proposal) => {
      if (!proposal?.id || !workflowContext?.rejectAgentAction) return;
      try {
        await workflowContext.rejectAgentAction(proposal.id);
        updateLocalProposalStatus(proposal.id, "rejected");
      } catch (error) {
        message.error(error.message || "Could not reject that proposal.");
      }
    },
    [updateLocalProposalStatus, workflowContext],
  );

  /* ── markdown renderers ────────────────────────────────────────────────── */
  const mdComponents = {
    p: ({ children }) => (
      <p style={{ margin: "0 0 8px", lineHeight: 1.45 }}>{children}</p>
    ),
    h1: ({ children }) => (
      <h3 style={{ margin: "10px 0 6px", fontSize: 16 }}>{children}</h3>
    ),
    h2: ({ children }) => (
      <h3 style={{ margin: "10px 0 6px", fontSize: 15 }}>{children}</h3>
    ),
    h3: ({ children }) => (
      <h4 style={{ margin: "8px 0 4px", fontSize: 14 }}>{children}</h4>
    ),
    ul: ({ children }) => (
      <ul style={{ paddingLeft: "18px", margin: "6px 0" }}>{children}</ul>
    ),
    ol: ({ children }) => (
      <ol style={{ paddingLeft: "18px", margin: "6px 0" }}>{children}</ol>
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
                Project Manager
              </Text>
              <Text type="secondary" style={{ display: "block", fontSize: 12 }}>
                Orchestrates specialist workflow agents
              </Text>
            </div>
            <Tag color="#111827" style={{ marginInlineEnd: 0 }}>
              Orchestrator
            </Tag>
          </Space>
          <Space>
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={onClose}
              size="small"
              aria-label="Close assistant"
            />
          </Space>
        </div>

        {/* messages */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: "14px",
            background: "#f6f5f2",
          }}
        >
          <List
            dataSource={messages}
            renderItem={(message, index) => {
              const isLast = index === messages.length - 1;
              const isUser = message.role === "user";
              const consultedAgents = isUser ? [] : messageAgents(message);
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
                      background: isUser
                        ? "var(--seg-accent-primary, #3f37c9)"
                        : "#ffffff",
                      color: isUser ? "white" : "black",
                      border: isUser ? "none" : "1px solid #e5e7eb",
                      boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05)",
                    }}
                  >
                    {isUser ? (
                      <Text style={{ color: "white" }}>{message.content}</Text>
                    ) : (
                      <Space
                        direction="vertical"
                        size={10}
                        style={{ width: "100%" }}
                      >
                        {consultedAgents.length > 0 && (
                          <div
                            aria-label="Consulted workflow agents"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: 6,
                              marginBottom: 2,
                            }}
                          >
                            <Text
                              type="secondary"
                              style={{
                                fontSize: 11,
                                lineHeight: "18px",
                                fontFamily: MONO_FONT,
                              }}
                            >
                              Agents
                            </Text>
                            {consultedAgents.map((agent) => (
                              <AgentBadge
                                key={agent.key}
                                agent={agent}
                                compact
                              />
                            ))}
                          </div>
                        )}
                        {message.trace?.length > 0 && (
                          <AssistantTrace trace={message.trace} />
                        )}
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
                            {message.proposals?.map((proposal) => {
                              const payload = proposal?.payload || {};
                              const params = payload?.params || {};
                              const actionCard =
                                params?.action_card ||
                                payload?.action_card ||
                                proposal?.action_card ||
                                {};
                              const actionTrace = toList(
                                params?.trace ||
                                  payload?.trace ||
                                  proposal?.trace ||
                                  actionCard?.trace,
                              );
                              const proposalTrace = toList(
                                proposal.trace ||
                                  payload?.trace ||
                                  params?.trace,
                              );
                              const specialistAgent =
                                params?.specialist_agent ||
                                payload?.specialist_agent ||
                                actionCard?.specialist_agent ||
                                proposal?.specialist_agent;
                              const orchestratorAgent =
                                params?.orchestrator_agent ||
                                payload?.orchestrator_agent ||
                                actionCard?.orchestrator_agent ||
                                proposal?.orchestrator_agent;
                              const workflowId =
                                proposal.workflow_id ||
                                proposal.workflowId ||
                                message.workflow_id;

                              return (
                                <AgentProposalCard
                                  key={proposal.id}
                                  proposal={{
                                    ...(payload || {}),
                                    ...(params || {}),
                                    specialist_agent: specialistAgent,
                                    orchestrator_agent: orchestratorAgent,
                                    action_card: actionCard,
                                    id: proposal.id,
                                    workflow_id: workflowId,
                                    approval_status: proposal.approval_status,
                                    type:
                                      payload.action ||
                                      proposal.type ||
                                      "agent_proposal",
                                    rationale: proposal.summary,
                                  }}
                                  onApprove={(_cardProposal, overrides) =>
                                    handleApproveProposal(
                                      {
                                        ...proposal,
                                        workflow_id: workflowId,
                                      },
                                      overrides,
                                    )
                                  }
                                  onReject={() =>
                                    handleRejectProposal({
                                      ...proposal,
                                      workflow_id: workflowId,
                                    })
                                  }
                                  trace={[...actionTrace, ...proposalTrace]}
                                />
                              );
                            })}
                          </div>
                        )}
                      </Space>
                    )}
                  </div>
                </List.Item>
              );
            }}
          />
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
