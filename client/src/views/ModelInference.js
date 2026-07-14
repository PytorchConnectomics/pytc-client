import React, { useCallback, useContext, useEffect, useRef, useState } from "react";
import { Button, Space } from "antd";
import {
  getInferenceLogs,
  getInferenceStatus,
  syncWorkflowInferenceRuntime,
  stopModelInference,
} from "../api";
import Configurator from "../components/Configurator";
import RuntimeLogPanel from "../components/RuntimeLogPanel";
import StageHeader from "../components/workflow/StageHeader";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";
import { getPathValue, launchInferenceFromContext } from "../runtime/modelLaunch";

function ModelInference({ isInferring, setIsInferring }) {
  const context = useContext(AppContext);
  const workflowContext = useWorkflow();
  const appendWorkflowEvent = workflowContext?.appendEvent;
  const workflowId = workflowContext?.workflow?.id;
  const workflowStage = workflowContext?.workflow?.stage || "inference";
  const pendingRuntimeAction = workflowContext?.pendingRuntimeAction;
  const consumeRuntimeAction = workflowContext?.consumeRuntimeAction;
  const refreshWorkflow = workflowContext?.refreshWorkflow;
  const refreshWorkflowEvents = workflowContext?.refreshEvents;
  const refreshWorkflowInsights = workflowContext?.refreshInsights;
  const refreshWorkflowEvidence = workflowContext?.refreshEvidence;
  const inference = context.inferenceState;
  const [inferenceStatus, setInferenceStatus] = useState("");
  const [inferenceRuntime, setInferenceRuntime] = useState(null);
  const pollingIntervalRef = useRef(null);
  const terminalLoggedRef = useRef(false);

  const refreshInferenceLogs = async () => {
    try {
      const runtime = await getInferenceLogs();
      setInferenceRuntime(runtime);
      return runtime;
    } catch (error) {
      console.error("Error loading inference logs:", error);
      return null;
    }
  };

  useEffect(() => {
    refreshInferenceLogs();
  }, []);

  useEffect(() => {
    if (isInferring) {
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const [status, runtime] = await Promise.all([
            getInferenceStatus(),
            getInferenceLogs(),
          ]);
          setInferenceRuntime(runtime);

          if (!status.isRunning) {
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
            setIsInferring(false);
            const succeeded = status.exitCode === 0;
            let syncResult = null;
            let syncError = null;
            if (workflowId) {
              try {
                syncResult = await syncWorkflowInferenceRuntime(workflowId);
                if (syncResult?.synced) {
                  await Promise.all([
                    refreshWorkflow?.(),
                    refreshWorkflowEvents?.(),
                    refreshWorkflowInsights?.(),
                    refreshWorkflowEvidence?.(),
                  ]);
                }
              } catch (error) {
                syncError = error;
                console.warn("Model run artifact sync failed:", error);
              }
            }
            if (!terminalLoggedRef.current && appendWorkflowEvent) {
              terminalLoggedRef.current = true;
              if (!syncResult?.synced) {
                await appendWorkflowEvent({
                  actor: "system",
                  event_type: succeeded
                    ? "inference.completed"
                    : "inference.failed",
                  stage: "inference",
                  summary: succeeded
                    ? "Model run completed, but runtime artifact sync did not complete."
                    : "Model run finished without a successful exit.",
                  payload: {
                    exitCode: status.exitCode,
                    phase: status.phase,
                    lastError: status.lastError,
                    outputPath: getPathValue(inference.outputPath),
                    syncReason: syncResult?.reason || null,
                    syncError: syncError?.message || null,
                  },
                });
              }
            }
            if (status.exitCode === 0) {
              console.log("Model run completed successfully.", status);
              setInferenceStatus(
                syncResult?.synced
                  ? `Model run completed and workflow synced: ${syncResult.outputPath || "prediction artifact captured"} ✓`
                  : "Model run completed successfully; workflow sync is pending. ✓",
              );
            } else if (status.exitCode !== null && status.exitCode !== undefined) {
              console.error("Model run failed.", status);
              setInferenceStatus(
                `Model run finished with exit code: ${status.exitCode}`,
              );
            } else if (status.phase === "failed" && status.lastError) {
              console.error("Model run failed.", status);
              setInferenceStatus(`Model run failed: ${status.lastError}`);
            } else {
              console.warn("Model run stopped.", status);
              setInferenceStatus("Model run stopped.");
            }
          }
        } catch (error) {
          console.error("Error polling inference status:", error);
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          setIsInferring(false);
          if (!terminalLoggedRef.current && appendWorkflowEvent) {
            terminalLoggedRef.current = true;
            await appendWorkflowEvent({
              actor: "system",
              event_type: "inference.failed",
              stage: "inference",
              summary: "Model run status polling failed.",
              payload: {
                error: error.message || "unknown error",
                outputPath: getPathValue(inference.outputPath),
              },
            });
          }
          setInferenceStatus(
            `Model run status polling failed: ${error.message || "unknown error"}`,
          );
        }
      }, 2000);
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [
    appendWorkflowEvent,
    inference.outputPath,
    isInferring,
    refreshWorkflow,
    refreshWorkflowEvidence,
    refreshWorkflowEvents,
    refreshWorkflowInsights,
    setIsInferring,
    workflowId,
  ]);

  const startInferenceRun = useCallback(async (runtimeAction = null) => {
    let checkpointPath = "";
    if (isInferring) {
      setInferenceStatus("A model run is already running.");
      return;
    }
    try {
      setIsInferring(true);
      setInferenceStatus("Starting model run...");
      terminalLoggedRef.current = false;

      checkpointPath = getPathValue(
        runtimeAction?.overrides?.checkpointPath ?? inference.checkpointPath,
      );

      const res = await launchInferenceFromContext(
        context,
        workflowId,
        runtimeAction?.overrides || {},
      );
      console.log(res);
      await refreshInferenceLogs();
      setInferenceStatus("Model run started. Monitoring process...");
    } catch (e) {
      console.log(e);
      setIsInferring(false);
      if (runtimeAction && appendWorkflowEvent) {
        await appendWorkflowEvent({
          actor: "system",
          event_type: "assistant.command_failed",
          stage: workflowStage,
          summary: "Assistant could not start the model run.",
          payload: {
            error: e.message || "unknown error",
            runtime_action: runtimeAction.kind,
          },
        });
      }
      if (!terminalLoggedRef.current && appendWorkflowEvent) {
        terminalLoggedRef.current = true;
        await appendWorkflowEvent({
          actor: "system",
          event_type: "inference.failed",
          stage: workflowStage,
          summary: "Model run failed to start.",
          payload: {
            error: e.message || "unknown error",
            outputPath: getPathValue(inference.outputPath),
            checkpointPath,
          },
        });
      }
      await refreshInferenceLogs();
      setInferenceStatus(
        `Model run error: ${e.message || "Please check console for details."}`,
      );
    }
  }, [
    appendWorkflowEvent,
    context,
    inference.checkpointPath,
    inference.outputPath,
    isInferring,
    setIsInferring,
    workflowId,
    workflowStage,
  ]);

  useEffect(() => {
    if (pendingRuntimeAction?.kind !== "start_inference") return;
    const action = pendingRuntimeAction;
    consumeRuntimeAction?.(action.id);
    startInferenceRun(action);
  }, [consumeRuntimeAction, pendingRuntimeAction, startInferenceRun]);

  const handleStartButton = async () => {
    await startInferenceRun();
  };

  const handleStopButton = async () => {
    try {
      setInferenceStatus("Stopping model run...");
      await stopModelInference();
    } catch (e) {
      console.log(e);
      setInferenceStatus(
        `Error stopping model run: ${e.message || "Please check console for details."}`,
      );
    } finally {
      setIsInferring(false);
      await refreshInferenceLogs();
    }
  };

  const [componentSize] = useState("default");

  return (
    <>
      <div>
        <div style={{ marginBottom: 12 }}>
          <StageHeader
            stage="inference"
            title="Run Model"
            subtitle="Run prediction, register output artifacts, and route failures into proofreading."
          />
        </div>
        <Configurator fileList={context.files} type="inference" />
        <Space wrap style={{ marginTop: 12 }} size={componentSize}>
          <Button
            onClick={handleStartButton}
            disabled={isInferring} // Disables the button when inference is running
            style={{ marginRight: "8px" }}
          >
            Run Model
          </Button>
          <Button
            onClick={handleStopButton}
            disabled={!isInferring} // Disables the button when inference is not running
          >
            Stop Run
          </Button>
        </Space>
        <p style={{ marginTop: 4 }}>{inferenceStatus}</p>
        <RuntimeLogPanel
          title="Run Model Runtime"
          runtime={inferenceRuntime}
          onRefresh={refreshInferenceLogs}
        />
      </div>
    </>
  );
}

export default ModelInference;
