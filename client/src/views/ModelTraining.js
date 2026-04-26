//  global localStorage
import React, { useCallback, useContext, useState, useEffect, useRef } from "react";
import { Button, Space, Tag, Typography } from "antd";
import {
  getTrainingLogs,
  stopModelTraining,
  getTrainingStatus,
} from "../api";
import Configurator from "../components/Configurator";
import RuntimeLogPanel from "../components/RuntimeLogPanel";
import StageHeader from "../components/workflow/StageHeader";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";
import { revealInFinder } from "../electronApi";
import { getPathValue, launchTrainingFromContext } from "../runtime/modelLaunch";

const { Text } = Typography;

function getBaseName(pathValue) {
  if (!pathValue) return "";
  const normalized = String(pathValue).replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || "";
}

function ModelTraining() {
  const context = useContext(AppContext);
  const workflowContext = useWorkflow();
  const appendWorkflowEvent = workflowContext?.appendEvent;
  const updateWorkflow = workflowContext?.updateWorkflow;
  const runClientEffects = workflowContext?.runClientEffects;
  const workflowId = workflowContext?.workflow?.id;
  const workflowStage = workflowContext?.workflow?.stage || "retraining_staged";
  const pendingRuntimeAction = workflowContext?.pendingRuntimeAction;
  const consumeRuntimeAction = workflowContext?.consumeRuntimeAction;
  const training = context.trainingState;
  const setInferenceConfig = context?.setInferenceConfig;
  const setInferenceCheckpointPath = context?.inferenceState?.setCheckpointPath;
  const setInferenceConfigOriginPath = context?.inferenceState?.setConfigOriginPath;
  const setInferenceSelectedYamlPreset =
    context?.inferenceState?.setSelectedYamlPreset;
  const setInferenceUploadedYamlFile =
    context?.inferenceState?.setUploadedYamlFile;
  const [isTraining, setIsTraining] = useState(false);
  const [trainingStatus, setTrainingStatus] = useState("");
  const [trainingRuntime, setTrainingRuntime] = useState(null);
  const pollingIntervalRef = useRef(null);
  const terminalLoggedRef = useRef(false);
  const latestCheckpointPath = getPathValue(
    trainingRuntime?.metadata?.latestCheckpointPath ||
      trainingRuntime?.metadata?.checkpointPath,
  );
  const latestCheckpointName = getBaseName(latestCheckpointPath);
  const resolvedTrainingOutputPath = getPathValue(
    trainingRuntime?.metadata?.outputPath || training.outputPath,
  );

  const refreshTrainingLogs = useCallback(async () => {
    try {
      const runtime = await getTrainingLogs();
      setTrainingRuntime(runtime);
      return runtime;
    } catch (error) {
      console.error("Error loading training logs:", error);
      return null;
    }
  }, []);

  const refreshTrainingRuntime = useCallback(async () => {
    const [status, runtime] = await Promise.all([
      getTrainingStatus(),
      getTrainingLogs(),
    ]);
    setTrainingRuntime(runtime);
    console.log("Training status:", status);

    if (!status.isRunning) {
      setIsTraining(false);
      const runtimeMetadata = runtime?.metadata || {};
      const nextOutputPath = getPathValue(
        runtimeMetadata.outputPath || training.outputPath,
      );
      const nextCheckpointPath = getPathValue(
        runtimeMetadata.latestCheckpointPath || runtimeMetadata.checkpointPath,
      );
      const nextCheckpointName = getBaseName(nextCheckpointPath);
      let nextStage = workflowStage;

      if (status.exitCode === 0) {
        if (nextCheckpointPath) {
          setInferenceCheckpointPath?.(nextCheckpointPath);
        }
        if (context?.trainingConfig) {
          setInferenceConfig?.(context.trainingConfig);
          setInferenceConfigOriginPath?.(
            training.configOriginPath ||
              training.selectedYamlPreset ||
              getPathValue(training.uploadedYamlFile) ||
              "",
          );
          setInferenceSelectedYamlPreset?.(training.selectedYamlPreset || "");
          setInferenceUploadedYamlFile?.("");
        }
        if (updateWorkflow) {
          try {
            const patch = { stage: "evaluation" };
            if (nextOutputPath) {
              patch.training_output_path = nextOutputPath;
            }
            if (nextCheckpointPath) {
              patch.checkpoint_path = nextCheckpointPath;
            }
            const nextWorkflow = await updateWorkflow(patch);
            nextStage = nextWorkflow?.stage || "evaluation";
          } catch (error) {
            console.error("Error updating workflow after training success:", error);
            nextStage = "evaluation";
          }
        } else {
          nextStage = "evaluation";
        }
      }

      if (!terminalLoggedRef.current && appendWorkflowEvent) {
        terminalLoggedRef.current = true;
        const succeeded = status.exitCode === 0;
        await appendWorkflowEvent({
          actor: "system",
          event_type: succeeded ? "training.completed" : "training.failed",
          stage: succeeded ? nextStage : workflowStage,
          summary: succeeded
            ? "Training completed successfully."
            : "Training finished without a successful exit.",
          payload: {
            exitCode: status.exitCode,
            phase: status.phase,
            lastError: status.lastError,
            outputPath: nextOutputPath,
            checkpointPath: nextCheckpointPath || null,
            checkpointName: nextCheckpointName || null,
          },
        });
      }

      if (status.exitCode === 0) {
        console.log("Training completed successfully.", status);
        setTrainingStatus(
          nextCheckpointName
            ? `Model ready: ${nextCheckpointName}`
            : "Training completed successfully! ✓",
        );
      } else if (status.exitCode !== null) {
        console.error("Training failed.", status);
        setTrainingStatus(`Training finished with exit code: ${status.exitCode}`);
      } else if (status.phase === "failed" && status.lastError) {
        console.error("Training failed.", status);
        setTrainingStatus(`Training failed: ${status.lastError}`);
      } else {
        console.warn("Training stopped.", status);
        setTrainingStatus("Training stopped.");
      }

      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }
  }, [
    appendWorkflowEvent,
    context?.trainingConfig,
    setInferenceConfig,
    setInferenceConfigOriginPath,
    setInferenceCheckpointPath,
    setInferenceSelectedYamlPreset,
    setInferenceUploadedYamlFile,
    training.configOriginPath,
    training.outputPath,
    training.selectedYamlPreset,
    training.uploadedYamlFile,
    updateWorkflow,
    workflowStage,
  ]);

  const recordTrainingPollingFailure = useCallback(async (error) => {
    if (!terminalLoggedRef.current && appendWorkflowEvent) {
      terminalLoggedRef.current = true;
      await appendWorkflowEvent({
        actor: "system",
        event_type: "training.failed",
        stage: workflowStage,
        summary: "Training status polling failed.",
        payload: {
          error: error.message || "unknown error",
          outputPath: getPathValue(training.outputPath),
        },
      });
    }
  }, [appendWorkflowEvent, training.outputPath, workflowStage]);

  useEffect(() => {
    refreshTrainingLogs();
  }, [refreshTrainingLogs]);

  // Poll training status when training is active
  useEffect(() => {
    if (isTraining) {
      console.log("Starting training status polling...");
      pollingIntervalRef.current = setInterval(async () => {
        try {
          await refreshTrainingRuntime();
        } catch (error) {
          console.error("Error polling training status:", error);
          setIsTraining(false);
          await recordTrainingPollingFailure(error);
          setTrainingStatus(
            `Training status polling failed: ${error.message || "unknown error"}`,
          );
        }
      }, 2000); // Poll every 2 seconds
    }

    // Cleanup on unmount or when training stops
    return () => {
      if (pollingIntervalRef.current) {
        console.log("Clearing polling interval");
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isTraining, recordTrainingPollingFailure, refreshTrainingRuntime]);

  const startTrainingRun = useCallback(async (runtimeAction = null) => {
    if (isTraining) {
      setTrainingStatus("Training is already running.");
      return;
    }
    try {
      setIsTraining(true);
      setTrainingStatus(
        "Starting training... Please wait, this may take a while.",
      );
      terminalLoggedRef.current = false;

      const res = await launchTrainingFromContext(
        context,
        workflowId,
        runtimeAction?.overrides || {},
      );
      console.log(res);
      await refreshTrainingLogs();

      setTrainingStatus(
        "Training started successfully. Monitoring progress...",
      );
    } catch (e) {
      console.error("Training start error:", e);
      if (runtimeAction && appendWorkflowEvent) {
        await appendWorkflowEvent({
          actor: "system",
          event_type: "assistant.command_failed",
          stage: workflowStage,
          summary: "Assistant could not start training.",
          payload: {
            error: e.message || "unknown error",
            runtime_action: runtimeAction.kind,
          },
        });
      }
      await refreshTrainingLogs();
      setTrainingStatus(
        `Training error: ${e.message || "Please check console for details."}`,
      );
      setIsTraining(false);
    }
  }, [
    appendWorkflowEvent,
    context,
    isTraining,
    refreshTrainingLogs,
    workflowId,
    workflowStage,
  ]);

  useEffect(() => {
    if (pendingRuntimeAction?.kind !== "start_training") return;
    const action = pendingRuntimeAction;
    consumeRuntimeAction?.(action.id);
    startTrainingRun(action);
  }, [consumeRuntimeAction, pendingRuntimeAction, startTrainingRun]);

  const handleStartButton = async () => {
    await startTrainingRun();
  };

  const handleStopButton = async () => {
    try {
      setTrainingStatus("Stopping training...");
      await stopModelTraining();
      setIsTraining(false);
      setTrainingStatus("Training stopped successfully.");
    } catch (e) {
      console.error("Training stop error:", e);
      setTrainingStatus(
        `Error stopping training: ${e.message || "Please check console for details."}`,
      );
    } finally {
      await refreshTrainingLogs();
    }
  };

  const handleOpenInference = useCallback(async () => {
    const effects = { navigate_to: "inference" };
    if (latestCheckpointPath) {
      setInferenceCheckpointPath?.(latestCheckpointPath);
      effects.set_inference_checkpoint_path = latestCheckpointPath;
    }
    await runClientEffects?.(effects);
  }, [latestCheckpointPath, runClientEffects, setInferenceCheckpointPath]);

  const handleOpenTensorboard = useCallback(async () => {
    await runClientEffects?.({ navigate_to: "monitoring" });
  }, [runClientEffects]);

  const handleRevealOutput = useCallback(async () => {
    if (!resolvedTrainingOutputPath) return;
    try {
      await revealInFinder(resolvedTrainingOutputPath);
    } catch (error) {
      console.error("Error revealing training output:", error);
    }
  }, [resolvedTrainingOutputPath]);

  // const handleTensorboardButton = async () => {
  //   try {
  //     const res = await startTensorboard();
  //     console.log(res);
  //     setTensorboardURL(res);
  //   } catch (e) {
  //     console.log(e);
  //   }
  // };
  // const [componentSize, setComponentSize] = useState("default");
  // const onFormLayoutChange = ({ size }) => {
  //   setComponentSize(size);
  // };

  return (
    <>
      <div>
        {/* {"ModelTraining"} */}
        <div style={{ marginBottom: 12 }}>
          <StageHeader
            stage={workflowStage}
            title="Model Training"
            subtitle="Train a candidate model from staged corrections and register the resulting checkpoint."
          />
        </div>
        <Configurator fileList={context.files} type="training" />
        <Space wrap style={{ marginTop: 12 }}>
          <Button onClick={handleStartButton} disabled={isTraining}>
            Start Training
          </Button>
          <Button onClick={handleStopButton} disabled={!isTraining}>
            Stop Training
          </Button>
        </Space>
        <p style={{ marginTop: 4 }}>{trainingStatus}</p>
        {trainingRuntime?.phase === "finished" && (
          <div
            style={{
              marginTop: 12,
              padding: "12px 14px",
              borderRadius: 8,
              border: "1px solid #d9f7be",
              background: "#f6ffed",
            }}
          >
            <Space direction="vertical" size={6} style={{ display: "flex" }}>
              <Space size={8} wrap>
                <Text strong>
                  {latestCheckpointName ? "Model Ready" : "Training Complete"}
                </Text>
                {latestCheckpointName && (
                  <Tag color="success" style={{ margin: 0 }}>
                    {latestCheckpointName}
                  </Tag>
                )}
              </Space>
              {resolvedTrainingOutputPath && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {`Output: ${getBaseName(resolvedTrainingOutputPath) || resolvedTrainingOutputPath}`}
                </Text>
              )}
              <Space wrap size={8}>
                <Button size="small" type="primary" onClick={handleOpenInference}>
                  Open Inference
                </Button>
                <Button size="small" onClick={handleOpenTensorboard}>
                  TensorBoard
                </Button>
                <Button
                  size="small"
                  onClick={handleRevealOutput}
                  disabled={!resolvedTrainingOutputPath}
                >
                  Show Output
                </Button>
              </Space>
            </Space>
          </div>
        )}
        <RuntimeLogPanel
          title="Training Runtime Log"
          runtime={trainingRuntime}
          onRefresh={refreshTrainingLogs}
        />
      </div>
    </>
  );
}

export default ModelTraining;
