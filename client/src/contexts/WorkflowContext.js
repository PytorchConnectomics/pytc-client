import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
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
  getWorkflowOverview,
  getWorkflowPreflight,
  getWorkflowProjectProgress,
  listWorkflowArtifacts,
  listWorkflowCorrectionSets,
  listWorkflowEvents,
  listWorkflowEvaluationResults,
  listWorkflowModelRuns,
  listWorkflowModelVersions,
  mountProjectDirectory,
  queryWorkflowAgent,
  rejectAgentAction as rejectAgentActionApi,
  resetFileWorkspace,
  runWorkflowCommand,
  startNewWorkflow as startNewWorkflowApi,
  stopModelInference,
  stopModelTraining,
  updateWorkflow as updateWorkflowApi,
  updateWorkflowProjectProgressVolume,
} from "../api";
import { AppContext } from "./GlobalContext";
import { logClientEvent } from "../logging/appEventLog";

export const WorkflowContext = createContext(null);

const PENDING_RUNTIME_ACTION_KEY = "pytc.workflow.pendingRuntimeAction.v1";
const PENDING_RUNTIME_ACTION_TTL_MS = 6 * 60 * 60 * 1000;
const PERSISTABLE_RUNTIME_KINDS = new Set(["monitor_training"]);

const isPersistableRuntimeAction = (kind) =>
  PERSISTABLE_RUNTIME_KINDS.has(kind);

const readPersistedRuntimeAction = (workflowId = null) => {
  if (typeof window === "undefined" || !window.sessionStorage) return null;
  if (!workflowId) return null;

  try {
    const raw = window.sessionStorage.getItem(PENDING_RUNTIME_ACTION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      parsed?.kind !== "pending_runtime_action" ||
      parsed?.workflowId !== workflowId ||
      !parsed?.action?.kind
    ) {
      if (parsed?.kind || parsed?.action) {
        window.sessionStorage.removeItem(PENDING_RUNTIME_ACTION_KEY);
      }
      return null;
    }
    const savedAt = Number(parsed.savedAt || 0);
    const age = Date.now() - savedAt;
    if (!Number.isFinite(age) || age > PENDING_RUNTIME_ACTION_TTL_MS) {
      window.sessionStorage.removeItem(PENDING_RUNTIME_ACTION_KEY);
      return null;
    }
    return parsed.action;
  } catch {
    return null;
  }
};

const writePersistedRuntimeAction = (workflowId = null, action = null) => {
  if (typeof window === "undefined" || !window.sessionStorage) return;
  if (!workflowId || !action) {
    window.sessionStorage.removeItem(PENDING_RUNTIME_ACTION_KEY);
    return;
  }
  try {
    window.sessionStorage.setItem(
      PENDING_RUNTIME_ACTION_KEY,
      JSON.stringify({
        kind: "pending_runtime_action",
        workflowId,
        action,
        savedAt: Date.now(),
      }),
    );
  } catch {
    // Persisting pending runtime actions is best-effort; it should not block runtime.
  }
};

export function useWorkflow() {
  return useContext(WorkflowContext);
}

const buildRuntimeOverridesFromEffects = (
  effects = {},
  {
    resolvedTrainingConfig = "",
    resolvedTrainingConfigOrigin = "",
    resolvedInferenceConfig = "",
    resolvedInferenceConfigOrigin = "",
  } = {},
) => ({
  inputLabelPath:
    effects.set_training_label_path || effects.set_inference_label_path || "",
  inputImagePath:
    effects.set_training_image_path || effects.set_inference_image_path || "",
  logPath: effects.set_training_log_path || "",
  outputPath:
    effects.set_training_output_path || effects.set_inference_output_path || "",
  trainingConfig: resolvedTrainingConfig || undefined,
  configOriginPath: resolvedTrainingConfigOrigin || undefined,
  autoParameters: Boolean(effects.runtime_action?.autopick_parameters),
  checkpointPath: effects.set_inference_checkpoint_path || "",
  inferenceConfig: resolvedInferenceConfig || undefined,
  inferenceConfigOriginPath: resolvedInferenceConfigOrigin || undefined,
  inferenceInputImagePath: effects.set_inference_image_path || "",
  inferenceInputLabelPath: effects.set_inference_label_path || "",
  datasetPath: effects.set_proofreading_dataset_path || "",
  maskPath: effects.set_proofreading_mask_path || "",
  projectName: effects.set_proofreading_project_name || "",
  visualizationImagePath: effects.set_visualization_image_path || "",
  visualizationLabelPath: effects.set_visualization_label_path || "",
  visualizationScales: effects.set_visualization_scales || "",
});

export function WorkflowProvider({ children }) {
  const appContext = useContext(AppContext);
  const [workflow, setWorkflow] = useState(null);
  const [events, setEvents] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [impactPreview, setImpactPreview] = useState(null);
  const [agentRecommendation, setAgentRecommendation] = useState(null);
  const [preflight, setPreflight] = useState(null);
  const [workflowOverview, setWorkflowOverview] = useState(null);
  const [projectProgress, setProjectProgress] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  const [modelRuns, setModelRuns] = useState([]);
  const [modelVersions, setModelVersions] = useState([]);
  const [correctionSets, setCorrectionSets] = useState([]);
  const [evaluationResults, setEvaluationResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastClientEffects, setLastClientEffects] = useState(null);
  const [pendingRuntimeAction, setPendingRuntimeAction] = useState(null);
  const hydratedPendingRuntimeRef = useRef(false);

  const clearPersistedRuntimeAction = useCallback(() => {
    writePersistedRuntimeAction(null, null);
  }, []);

  const registerPendingRuntimeAction = useCallback(
    (action, persist = false) => {
      if (!action) return;
      const nextAction = {
        id: action.id || `${action.kind}:${Date.now()}`,
        ...action,
      };
      setPendingRuntimeAction(nextAction);
      const shouldPersist = persist || isPersistableRuntimeAction(action.kind);
      if (shouldPersist) {
        writePersistedRuntimeAction(workflow?.id, nextAction);
      } else if (workflow?.id) {
        writePersistedRuntimeAction(workflow?.id, null);
      }
      return nextAction;
    },
    [workflow?.id],
  );

  const clientEffectsWithoutRuntime = useCallback((effects) => {
    if (!effects || typeof effects !== "object") return effects;
    const { runtime_action: _runtimeAction, ...rest } = effects;
    return rest;
  }, []);

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

  const applyWorkflowDetail = useCallback((data) => {
    setWorkflow(data?.workflow || null);
    setEvents(data?.events || []);
    setHotspots([]);
    setImpactPreview(null);
    setAgentRecommendation(null);
    setPreflight(null);
    setWorkflowOverview(null);
    setProjectProgress(null);
    setArtifacts([]);
    setModelRuns([]);
    setModelVersions([]);
    setCorrectionSets([]);
    setEvaluationResults([]);
    setLastClientEffects(null);
    setPendingRuntimeAction(null);
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

  const refreshPreflight = useCallback(async () => {
    if (!workflow?.id) {
      setPreflight(null);
      return null;
    }
    try {
      const nextPreflight = await getWorkflowPreflight(workflow.id);
      setPreflight(nextPreflight || null);
      return nextPreflight || null;
    } catch (error) {
      console.warn("Workflow preflight refresh failed:", error);
      return null;
    }
  }, [workflow?.id]);

  const refreshProjectProgress = useCallback(async () => {
    if (!workflow?.id) {
      setProjectProgress(null);
      return null;
    }
    try {
      const progress = await getWorkflowProjectProgress(workflow.id);
      setProjectProgress(progress || null);
      return progress || null;
    } catch (error) {
      console.warn("Workflow project progress refresh failed:", error);
      return null;
    }
  }, [workflow?.id]);

  const refreshWorkflowOverview = useCallback(
    async ({ refresh = true } = {}) => {
      if (!workflow?.id) {
        setWorkflowOverview(null);
        return null;
      }
      try {
        const overview = await getWorkflowOverview(workflow.id, { refresh });
        setWorkflowOverview(overview || null);
        if (overview?.project_progress) {
          setProjectProgress(overview.project_progress);
        }
        return overview || null;
      } catch (error) {
        console.warn("Workflow overview refresh failed:", error);
        return null;
      }
    },
    [workflow?.id],
  );

  const updateProjectProgressVolume = useCallback(
    async (body) => {
      if (!workflow?.id) return null;
      const progress = await updateWorkflowProjectProgressVolume(
        workflow.id,
        body,
      );
      setProjectProgress(progress || null);
      await refreshWorkflowOverview({ refresh: false });
      return progress || null;
    },
    [refreshWorkflowOverview, workflow?.id],
  );

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

  useEffect(() => {
    refreshPreflight();
  }, [
    workflow?.id,
    workflow?.stage,
    workflow?.dataset_path,
    workflow?.image_path,
    workflow?.label_path,
    workflow?.mask_path,
    workflow?.inference_output_path,
    workflow?.checkpoint_path,
    workflow?.config_path,
    workflow?.corrected_mask_path,
    workflow?.training_output_path,
    events.length,
    refreshPreflight,
  ]);

  useEffect(() => {
    refreshWorkflowOverview();
  }, [
    workflow?.id,
    workflow?.stage,
    workflow?.dataset_path,
    workflow?.image_path,
    workflow?.label_path,
    workflow?.mask_path,
    workflow?.inference_output_path,
    workflow?.checkpoint_path,
    workflow?.corrected_mask_path,
    workflow?.training_output_path,
    events.length,
    refreshWorkflowOverview,
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

  const clearLocalWorkflowInputs = useCallback(async () => {
    await appContext?.resetFileState?.();
    appContext?.setTrainingConfig?.(null);
    appContext?.setInferenceConfig?.(null);
    appContext?.setViewer?.(null);
    appContext?.setTensorBoardURL?.(null);
    appContext?.trainingState?.setConfigOriginPath?.("");
    appContext?.trainingState?.setUploadedYamlFile?.("");
    appContext?.trainingState?.setSelectedYamlPreset?.("");
    appContext?.trainingState?.setOutputPath?.(null);
    appContext?.trainingState?.setLogPath?.(null);
    appContext?.inferenceState?.setConfigOriginPath?.("");
    appContext?.inferenceState?.setUploadedYamlFile?.("");
    appContext?.inferenceState?.setSelectedYamlPreset?.("");
    appContext?.inferenceState?.setOutputPath?.(null);
    appContext?.inferenceState?.setCheckpointPath?.(null);
  }, [appContext]);

  const startNewWorkflow = useCallback(
    async (body = {}) => {
      await resetFileWorkspace();
      await clearLocalWorkflowInputs();
      const data = await startNewWorkflowApi(body);
      applyWorkflowDetail(data);
      return data;
    },
    [applyWorkflowDetail, clearLocalWorkflowInputs],
  );

  useEffect(() => {
    let cancelled = false;
    const resumeWorkflowSession = async () => {
      setLoading(true);
      try {
        const data = await getCurrentWorkflow();
        if (cancelled) return;
        applyWorkflowDetail(data);

        const mountedProjectPath = data?.workflow?.dataset_path;
        if (mountedProjectPath) {
          try {
            await mountProjectDirectory({
              directoryPath: mountedProjectPath,
              mountName: data?.workflow?.title || "",
              destinationPath: "root",
            });
          } catch (mountError) {
            console.warn("Initial project remount failed:", mountError);
          }
        }
      } catch (error) {
        console.warn("Workflow session resume failed:", error);
        if (!cancelled) {
          message.error("Failed to load workflow session.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    resumeWorkflowSession();
    return () => {
      cancelled = true;
    };
  }, [applyWorkflowDetail]);

  useEffect(() => {
    if (!workflow?.id) return;
    const workflowId = workflow.id;
    if (hydratedPendingRuntimeRef.current === workflowId) return;
    hydratedPendingRuntimeRef.current = workflowId;

    const restored = readPersistedRuntimeAction(workflowId);
    if (restored) {
      setPendingRuntimeAction(restored);
    } else {
      clearPersistedRuntimeAction();
    }
  }, [clearPersistedRuntimeAction, workflow?.id]);

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
      if (effects.set_inference_image_path && appContext?.inferenceState) {
        appContext.inferenceState.setInputImage?.(
          effects.set_inference_image_path,
        );
      }
      if (effects.set_inference_label_path && appContext?.inferenceState) {
        appContext.inferenceState.setInputLabel?.(
          effects.set_inference_label_path,
        );
      }
      if (effects.set_inference_output_path && appContext?.inferenceState) {
        appContext.inferenceState.setOutputPath(
          effects.set_inference_output_path,
        );
      }
      let resolvedInferenceConfig = "";
      let resolvedInferenceConfigOrigin = "";
      if (effects.set_inference_config_preset && appContext?.inferenceState) {
        try {
          const preset = await getConfigPresetContent(
            effects.set_inference_config_preset,
          );
          resolvedInferenceConfig = preset?.content || "";
          resolvedInferenceConfigOrigin =
            preset?.path || effects.set_inference_config_preset;
          if (resolvedInferenceConfig) {
            appContext.setInferenceConfig?.(resolvedInferenceConfig);
            appContext.inferenceState.setConfigOriginPath?.(
              resolvedInferenceConfigOrigin,
            );
            appContext.inferenceState.setSelectedYamlPreset?.(
              resolvedInferenceConfigOrigin,
            );
            appContext.inferenceState.setUploadedYamlFile?.("");
          }
        } catch (error) {
          logClientEvent("workflow_action_inference_preset_load_failed", {
            level: "ERROR",
            source: "workflow_context",
            message: error.message || "Inference preset load failed",
            data: {
              workflowId: workflow?.id || null,
              preset: effects.set_inference_config_preset,
            },
          });
          throw error;
        }
      }
      if (effects.set_visualization_image_path && appContext?.setCurrentImage) {
        appContext.setCurrentImage(effects.set_visualization_image_path);
      }
      if (effects.set_visualization_label_path && appContext?.setCurrentLabel) {
        appContext.setCurrentLabel(effects.set_visualization_label_path);
      }
      if (
        effects.set_visualization_scales &&
        appContext?.setVisualizationScales
      ) {
        const nextScales = Array.isArray(effects.set_visualization_scales)
          ? effects.set_visualization_scales.join(",")
          : String(effects.set_visualization_scales);
        appContext.setVisualizationScales(nextScales);
      }
      if (effects.runtime_action?.kind) {
        if (effects.runtime_action.kind === "stop_inference") {
          await stopModelInference();
          message.info("Inference stop requested.");
        } else if (effects.runtime_action.kind === "stop_training") {
          await stopModelTraining();
          message.info("Training stop requested.");
        }
        const nextRuntimeAction = {
          id: `${effects.runtime_action.kind}:${Date.now()}`,
          ...effects.runtime_action,
          overrides: buildRuntimeOverridesFromEffects(effects, {
            resolvedTrainingConfig,
            resolvedTrainingConfigOrigin,
            resolvedInferenceConfig,
            resolvedInferenceConfigOrigin,
          }),
        };
        registerPendingRuntimeAction(nextRuntimeAction);
      }
      if (effects.reset_workspace) {
        const resetResult = await resetFileWorkspace();
        await appContext?.resetFileState?.();
        if (workflow?.id) {
          await updateWorkflowApi(workflow.id, {
            metadata: {
              project_context: null,
              visualization_scales: null,
              visualization_scales_source: null,
              active_volume_pair: null,
              needs_project_context: true,
            },
          });
          await refreshWorkflow();
        }
        message.success(
          `Workspace reset. Removed ${resetResult?.deleted_count ?? 0} indexed item(s).`,
        );
      }
      if (effects.start_new_workflow) {
        const resetBody =
          typeof effects.start_new_workflow === "object"
            ? effects.start_new_workflow
            : {};
        await resetFileWorkspace();
        await clearLocalWorkflowInputs();
        await startNewWorkflowApi(resetBody);
        await refreshWorkflow();
      }
      if (effects.mount_project?.directory_path) {
        const mountResult = await mountProjectDirectory({
          directoryPath: effects.mount_project.directory_path,
          mountName: effects.mount_project.mount_name || "",
          destinationPath: effects.mount_project.destination_path || "root",
        });
        message.success(mountResult?.message || "Project mounted.");
        if (effects.mount_project.workflow_patch && workflow?.id) {
          await updateWorkflowApi(
            workflow.id,
            effects.mount_project.workflow_patch,
          );
        }
        await refreshWorkflow();
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
      if (effects.refresh_project_progress) {
        await refreshProjectProgress();
      }
      await refreshAgentRecommendation();
      setLastClientEffects({ ...effects });
    },
    [
      appContext,
      clearLocalWorkflowInputs,
      registerPendingRuntimeAction,
      refreshAgentRecommendation,
      refreshEvidence,
      refreshEvents,
      refreshWorkflow,
      refreshInsights,
      refreshProjectProgress,
      workflow?.corrected_mask_path,
      workflow?.id,
    ],
  );

  const consumeRuntimeAction = useCallback(
    (actionId = null) => {
      setPendingRuntimeAction((current) => {
        if (!current) return null;
        if (!actionId || current.id === actionId) {
          clearPersistedRuntimeAction();
          return null;
        }
        return current;
      });
    },
    [clearPersistedRuntimeAction],
  );

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
    async (eventId, overrides = {}) => {
      if (!workflow?.id) return null;
      const result = await approveAgentActionApi(
        workflow.id,
        eventId,
        overrides,
      );
      if (result?.workflow) {
        setWorkflow(result.workflow);
      }
      const durableCommand = result?.commands?.find?.((command) =>
        Number.isFinite(Number(command?.id)),
      );
      if (durableCommand) {
        const approvedEffects = result?.client_effects || {};
        await runClientEffects(clientEffectsWithoutRuntime(approvedEffects));
        const commandResult = await runWorkflowCommand(
          workflow.id,
          durableCommand.id,
        );
        if ((approvedEffects?.runtime_action || {}).kind === "start_training") {
          registerPendingRuntimeAction(
            {
              id: `monitor_training:${Date.now()}`,
              kind: "monitor_training",
              commandId: durableCommand.id,
              commandResult,
              clientEffects: approvedEffects,
              overrides: buildRuntimeOverridesFromEffects(approvedEffects),
            },
            true,
          );
        }
        await Promise.allSettled([
          refreshWorkflow(),
          refreshEvents(),
          refreshEvidence(),
          refreshAgentRecommendation(),
          refreshPreflight(),
          refreshWorkflowOverview(),
          refreshProjectProgress(),
        ]);
      } else {
        await runClientEffects(result?.client_effects);
      }
      await refreshEvents();
      message.success("Agent proposal approved.");
      return result;
    },
    [
      clientEffectsWithoutRuntime,
      registerPendingRuntimeAction,
      refreshAgentRecommendation,
      refreshEvents,
      refreshEvidence,
      refreshPreflight,
      refreshWorkflowOverview,
      refreshProjectProgress,
      refreshWorkflow,
      runClientEffects,
      workflow?.id,
    ],
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
      await Promise.allSettled([
        refreshWorkflow(),
        refreshAgentRecommendation(),
        refreshWorkflowOverview(),
        refreshProjectProgress(),
      ]);
      return result;
    },
    [
      workflow?.id,
      refreshEvents,
      refreshWorkflow,
      refreshAgentRecommendation,
      refreshWorkflowOverview,
      refreshProjectProgress,
    ],
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
        preflight,
        workflowOverview,
        projectProgress,
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
        refreshPreflight,
        refreshWorkflowOverview,
        refreshProjectProgress,
        updateProjectProgressVolume,
        refreshEvidence,
        startNewWorkflow,
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
