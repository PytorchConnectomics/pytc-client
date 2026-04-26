import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { message } from "antd";
import {
  appendWorkflowEvent,
  approveAgentAction as approveAgentActionApi,
  computeWorkflowEvaluationResult,
  createAgentAction,
  exportWorkflowBundle,
  getConfigPresetContent,
  getCurrentWorkflow,
  getWorkflowAgentRecommendation,
  getWorkflowHotspots,
  getWorkflowImpactPreview,
  listWorkflowArtifacts,
  listWorkflowCorrectionSets,
  listWorkflowEvents,
  listWorkflowEvaluationResults,
  listWorkflowModelRuns,
  listWorkflowModelVersions,
  queryWorkflowAgent,
  rejectAgentAction as rejectAgentActionApi,
  updateWorkflow as updateWorkflowApi,
} from "../api";
import { AppContext } from "./GlobalContext";
import { logClientEvent } from "../logging/appEventLog";

export const WorkflowContext = createContext(null);

export function useWorkflow() {
  return useContext(WorkflowContext);
}

export function WorkflowProvider({ children }) {
  const appContext = useContext(AppContext);
  const [workflow, setWorkflow] = useState(null);
  const [events, setEvents] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [impactPreview, setImpactPreview] = useState(null);
  const [agentRecommendation, setAgentRecommendation] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  const [modelRuns, setModelRuns] = useState([]);
  const [modelVersions, setModelVersions] = useState([]);
  const [correctionSets, setCorrectionSets] = useState([]);
  const [evaluationResults, setEvaluationResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastClientEffects, setLastClientEffects] = useState(null);
  const [pendingRuntimeAction, setPendingRuntimeAction] = useState(null);

  const refreshWorkflow = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCurrentWorkflow();
      setWorkflow(data?.workflow || null);
      setEvents(data?.events || []);
      return data;
    } catch (error) {
      message.error("Failed to load workflow state.");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshEvents = useCallback(async () => {
    if (!workflow?.id) return [];
    const nextEvents = await listWorkflowEvents(workflow.id);
    setEvents(nextEvents || []);
    return nextEvents || [];
  }, [workflow?.id]);

  const refreshInsights = useCallback(async () => {
    if (!workflow?.id) {
      setHotspots([]);
      setImpactPreview(null);
      return null;
    }
    try {
      const [hotspotData, impactData] = await Promise.all([
        getWorkflowHotspots(workflow.id),
        getWorkflowImpactPreview(workflow.id),
      ]);
      setHotspots(hotspotData?.hotspots || []);
      setImpactPreview(impactData || null);
      return {
        hotspots: hotspotData?.hotspots || [],
        impactPreview: impactData || null,
      };
    } catch (_error) {
      return null;
    }
  }, [workflow?.id]);

  const refreshAgentRecommendation = useCallback(async () => {
    if (!workflow?.id) {
      setAgentRecommendation(null);
      return null;
    }
    try {
      const recommendation = await getWorkflowAgentRecommendation(workflow.id);
      setAgentRecommendation(recommendation || null);
      return recommendation || null;
    } catch (error) {
      console.warn("Workflow agent recommendation refresh failed:", error);
      return null;
    }
  }, [workflow?.id]);

  const refreshEvidence = useCallback(async () => {
    if (!workflow?.id) {
      setArtifacts([]);
      setModelRuns([]);
      setModelVersions([]);
      setCorrectionSets([]);
      setEvaluationResults([]);
      return null;
    }
    try {
      const [
        nextArtifacts,
        nextModelRuns,
        nextModelVersions,
        nextCorrectionSets,
        nextEvaluationResults,
      ] = await Promise.all([
        listWorkflowArtifacts(workflow.id),
        listWorkflowModelRuns(workflow.id),
        listWorkflowModelVersions(workflow.id),
        listWorkflowCorrectionSets(workflow.id),
        listWorkflowEvaluationResults(workflow.id),
      ]);
      setArtifacts(nextArtifacts || []);
      setModelRuns(nextModelRuns || []);
      setModelVersions(nextModelVersions || []);
      setCorrectionSets(nextCorrectionSets || []);
      setEvaluationResults(nextEvaluationResults || []);
      return {
        artifacts: nextArtifacts || [],
        modelRuns: nextModelRuns || [],
        modelVersions: nextModelVersions || [],
        correctionSets: nextCorrectionSets || [],
        evaluationResults: nextEvaluationResults || [],
      };
    } catch (error) {
      console.warn("Workflow evidence refresh failed:", error);
      return null;
    }
  }, [workflow?.id]);

  useEffect(() => {
    refreshWorkflow();
  }, [refreshWorkflow]);

  useEffect(() => {
    if (!workflow?.id) {
      setHotspots([]);
      setImpactPreview(null);
      return;
    }
    refreshInsights();
  }, [
    workflow?.id,
    workflow?.stage,
    workflow?.corrected_mask_path,
    events.length,
    refreshInsights,
  ]);

  useEffect(() => {
    refreshEvidence();
  }, [
    workflow?.id,
    workflow?.stage,
    workflow?.inference_output_path,
    workflow?.corrected_mask_path,
    workflow?.training_output_path,
    events.length,
    refreshEvidence,
  ]);

  useEffect(() => {
    refreshAgentRecommendation();
  }, [
    workflow?.id,
    workflow?.stage,
    workflow?.inference_output_path,
    workflow?.corrected_mask_path,
    workflow?.training_output_path,
    events.length,
    refreshAgentRecommendation,
  ]);

  const updateWorkflow = useCallback(
    async (patch) => {
      if (!workflow?.id) return null;
      const nextWorkflow = await updateWorkflowApi(workflow.id, patch);
      setWorkflow(nextWorkflow);
      return nextWorkflow;
    },
    [workflow?.id],
  );

  const appendEvent = useCallback(
    async (event) => {
      if (!workflow?.id) return null;
      try {
        const nextEvent = await appendWorkflowEvent(workflow.id, event);
        if (nextEvent) {
          setEvents((prev) => [...prev, nextEvent]);
        }
        return nextEvent;
      } catch (error) {
        console.warn("Workflow event append failed:", error);
        return null;
      }
    },
    [workflow?.id],
  );

  const proposeAgentAction = useCallback(
    async (action) => {
      if (!workflow?.id) return null;
      const proposal = await createAgentAction(workflow.id, action);
      await refreshEvents();
      return proposal;
    },
    [workflow?.id, refreshEvents],
  );

  const runClientEffects = useCallback(
    async (effects) => {
      if (!effects) return;
      if (effects.set_training_label_path && appContext?.trainingState) {
        appContext.trainingState.setInputLabel(effects.set_training_label_path);
      }
      if (effects.set_training_image_path && appContext?.trainingState) {
        appContext.trainingState.setInputImage?.(
          effects.set_training_image_path,
        );
      }
      if (effects.set_training_log_path && appContext?.trainingState) {
        appContext.trainingState.setLogPath(effects.set_training_log_path);
      }
      if (effects.set_training_output_path && appContext?.trainingState) {
        appContext.trainingState.setOutputPath(
          effects.set_training_output_path,
        );
      }
      let resolvedTrainingConfig = "";
      let resolvedTrainingConfigOrigin = "";
      if (effects.set_training_config_preset && appContext?.trainingState) {
        try {
          const preset = await getConfigPresetContent(
            effects.set_training_config_preset,
          );
          resolvedTrainingConfig = preset?.content || "";
          resolvedTrainingConfigOrigin =
            preset?.path || effects.set_training_config_preset;
          if (resolvedTrainingConfig) {
            appContext.setTrainingConfig?.(resolvedTrainingConfig);
            appContext.trainingState.setConfigOriginPath?.(
              resolvedTrainingConfigOrigin,
            );
            appContext.trainingState.setSelectedYamlPreset?.(
              resolvedTrainingConfigOrigin,
            );
            appContext.trainingState.setUploadedYamlFile?.("");
          }
        } catch (error) {
          logClientEvent("workflow_action_training_preset_load_failed", {
            level: "ERROR",
            source: "workflow_context",
            message: error.message || "Training preset load failed",
            data: {
              workflowId: workflow?.id || null,
              preset: effects.set_training_config_preset,
            },
          });
          throw error;
        }
      }
      if (effects.set_inference_checkpoint_path && appContext?.inferenceState) {
        appContext.inferenceState.setCheckpointPath(
          effects.set_inference_checkpoint_path,
        );
      }
      if (effects.set_inference_output_path && appContext?.inferenceState) {
        appContext.inferenceState.setOutputPath(
          effects.set_inference_output_path,
        );
      }
      if (effects.runtime_action?.kind) {
        setPendingRuntimeAction({
          id: `${effects.runtime_action.kind}:${Date.now()}`,
          ...effects.runtime_action,
          overrides: {
            inputLabelPath: effects.set_training_label_path || "",
            inputImagePath: effects.set_training_image_path || "",
            logPath: effects.set_training_log_path || "",
            outputPath:
              effects.set_training_output_path ||
              effects.set_inference_output_path ||
              "",
            trainingConfig: resolvedTrainingConfig || undefined,
            configOriginPath: resolvedTrainingConfigOrigin || undefined,
            autoParameters: Boolean(
              effects.runtime_action?.autopick_parameters,
            ),
            checkpointPath: effects.set_inference_checkpoint_path || "",
            datasetPath: effects.set_proofreading_dataset_path || "",
            maskPath: effects.set_proofreading_mask_path || "",
            projectName: effects.set_proofreading_project_name || "",
          },
        });
      }
      if (effects.workflow_action?.kind === "propose_retraining_stage") {
        const correctedMaskPath =
          effects.workflow_action.corrected_mask_path ||
          workflow?.corrected_mask_path ||
          "";
        if (workflow?.id && correctedMaskPath) {
          await createAgentAction(workflow.id, {
            action: "stage_retraining_from_corrections",
            summary: "Stage corrected masks for retraining.",
            payload: { corrected_mask_path: correctedMaskPath },
          });
          await refreshEvents();
          message.info("Agent proposed a retraining handoff.");
        } else {
          message.warning("No corrected mask path is available to stage.");
        }
      }
      if (effects.workflow_action?.kind === "compute_evaluation") {
        const action = effects.workflow_action;
        logClientEvent("workflow_action_compute_evaluation_started", {
          source: "workflow_context",
          message: "Assistant-triggered evaluation started",
          data: { workflowId: workflow?.id || null },
        });
        if (
          !workflow?.id ||
          !action.baseline_prediction_path ||
          !action.candidate_prediction_path ||
          !action.ground_truth_path
        ) {
          message.warning(
            "Metrics need a previous result, a new result, and a reference mask.",
          );
        } else {
          try {
            const result = await computeWorkflowEvaluationResult(workflow.id, {
              name: action.name || "workflow-before-after-evaluation",
              baseline_prediction_path: action.baseline_prediction_path,
              candidate_prediction_path: action.candidate_prediction_path,
              ground_truth_path: action.ground_truth_path,
              baseline_run_id: action.baseline_run_id || undefined,
              candidate_run_id: action.candidate_run_id || undefined,
              model_version_id: action.model_version_id || undefined,
              metadata: action.metadata || { source: "workflow_agent" },
            });
            message.success(result?.summary || "Metrics computed.");
            await refreshEvidence();
            await refreshEvents();
            logClientEvent("workflow_action_compute_evaluation_completed", {
              source: "workflow_context",
              message: "Assistant-triggered evaluation completed",
              data: {
                workflowId: workflow.id,
                evaluationId: result?.id || null,
              },
            });
          } catch (error) {
            logClientEvent("workflow_action_compute_evaluation_failed", {
              level: "ERROR",
              source: "workflow_context",
              message: error.message || "Assistant-triggered evaluation failed",
              data: { workflowId: workflow.id },
            });
            throw error;
          }
        }
      }
      if (effects.workflow_action?.kind === "export_bundle") {
        logClientEvent("workflow_action_export_bundle_started", {
          source: "workflow_context",
          message: "Assistant-triggered evidence export started",
          data: { workflowId: workflow?.id || null },
        });
        if (!workflow?.id) return;
        try {
          const bundle = await exportWorkflowBundle(workflow.id);
          const missingCount = (bundle?.artifact_paths || []).filter(
            (entry) => !entry.exists,
          ).length;
          message.success(
            `Evidence exported: ${bundle?.artifacts?.length || 0} artifacts, ${missingCount} missing paths.`,
          );
          await refreshEvidence();
          await refreshEvents();
          logClientEvent("workflow_action_export_bundle_completed", {
            source: "workflow_context",
            message: "Assistant-triggered evidence export completed",
            data: { workflowId: workflow.id, missingCount },
          });
        } catch (error) {
          logClientEvent("workflow_action_export_bundle_failed", {
            level: "ERROR",
            source: "workflow_context",
            message:
              error.message || "Assistant-triggered evidence export failed",
            data: { workflowId: workflow.id },
          });
          throw error;
        }
      }
      if (effects.refresh_insights) {
        await refreshInsights();
      }
      await refreshAgentRecommendation();
      setLastClientEffects({ ...effects });
    },
    [
      appContext,
      refreshAgentRecommendation,
      refreshEvidence,
      refreshEvents,
      refreshInsights,
      workflow?.corrected_mask_path,
      workflow?.id,
    ],
  );

  const consumeRuntimeAction = useCallback((actionId = null) => {
    setPendingRuntimeAction((current) => {
      if (!current) return null;
      if (!actionId || current.id === actionId) {
        return null;
      }
      return current;
    });
  }, []);

  const executeAssistantItem = useCallback(
    async (item) => {
      if (!item) return;
      if (workflow?.id) {
        try {
          await appendEvent({
            actor: "user",
            event_type: "assistant.command.invoked",
            stage: workflow.stage,
            summary: `Executed assistant item: ${item.title || item.label || item.id || "action"}.`,
            payload: {
              item_id: item.id || null,
              item_label: item.title || item.label || null,
              item_type: item.command ? "command" : "action",
              runtime_action: item.client_effects?.runtime_action || null,
            },
          });
        } catch (_error) {
          // Do not block command execution on audit-log failures.
        }
      }
      await runClientEffects(item.client_effects);
    },
    [appendEvent, runClientEffects, workflow?.id, workflow?.stage],
  );

  const approveAgentAction = useCallback(
    async (eventId) => {
      if (!workflow?.id) return null;
      const result = await approveAgentActionApi(workflow.id, eventId);
      if (result?.workflow) {
        setWorkflow(result.workflow);
      }
      await runClientEffects(result?.client_effects);
      await refreshEvents();
      message.success("Agent proposal approved.");
      return result;
    },
    [workflow?.id, refreshEvents, runClientEffects],
  );

  const rejectAgentAction = useCallback(
    async (eventId) => {
      if (!workflow?.id) return null;
      const result = await rejectAgentActionApi(workflow.id, eventId);
      await refreshEvents();
      message.info("Agent proposal rejected.");
      return result;
    },
    [workflow?.id, refreshEvents],
  );

  const queryAgent = useCallback(
    async (query, conversationId = null) => {
      if (!workflow?.id) return null;
      const result = await queryWorkflowAgent(
        workflow.id,
        query,
        conversationId,
      );
      if (result?.proposals?.length) {
        await refreshEvents();
      }
      return result;
    },
    [workflow?.id, refreshEvents],
  );

  const consumeClientEffects = useCallback(() => {
    const effects = lastClientEffects;
    setLastClientEffects(null);
    return effects;
  }, [lastClientEffects]);

  return (
    <WorkflowContext.Provider
      value={{
        workflow,
        events,
        hotspots,
        impactPreview,
        agentRecommendation,
        artifacts,
        modelRuns,
        modelVersions,
        correctionSets,
        evaluationResults,
        loading,
        lastClientEffects,
        pendingRuntimeAction,
        refreshWorkflow,
        refreshEvents,
        refreshInsights,
        refreshAgentRecommendation,
        refreshEvidence,
        updateWorkflow,
        appendEvent,
        proposeAgentAction,
        approveAgentAction,
        rejectAgentAction,
        queryAgent,
        runClientEffects,
        executeAssistantItem,
        consumeRuntimeAction,
        consumeClientEffects,
      }}
    >
      {children}
    </WorkflowContext.Provider>
  );
}
