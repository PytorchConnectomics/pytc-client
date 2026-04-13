import React, { useContext, useEffect, useRef, useState } from "react";
import { Button, Space } from "antd";
import yaml from "js-yaml";
import {
  getInferenceLogs,
  getInferenceStatus,
  startModelInference,
  stopModelInference,
} from "../api";
import Configurator from "../components/Configurator";
import { applyInputPaths } from "../configSchema";
import RuntimeLogPanel from "../components/RuntimeLogPanel";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";

function ModelInference({ isInferring, setIsInferring }) {
  const context = useContext(AppContext);
  const workflowContext = useWorkflow();
  const appendWorkflowEvent = workflowContext?.appendEvent;
  const workflowId = workflowContext?.workflow?.id;
  const inference = context.inferenceState;
  const [inferenceStatus, setInferenceStatus] = useState("");
  const [inferenceRuntime, setInferenceRuntime] = useState(null);
  const pollingIntervalRef = useRef(null);
  const terminalLoggedRef = useRef(false);

  const getPath = (val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.path || val.originFileObj?.path || "";
  };

  const getConfigOriginPath = () => {
    return (
      inference.configOriginPath ||
      inference.selectedYamlPreset ||
      getPath(inference.uploadedYamlFile)
    );
  };

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

  const getPreparedInferenceConfig = (inferenceConfig) => {
    try {
      const yamlData = yaml.load(inferenceConfig);
      if (!yamlData || typeof yamlData !== "object") {
        return inferenceConfig;
      }

      applyInputPaths(yamlData, {
        mode: "inference",
        inputImagePath: getPath(inference.inputImage),
        inputLabelPath: "",
        inputPath: "",
        outputPath: getPath(inference.outputPath),
      });
      return yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
    } catch (error) {
      console.warn(
        "Failed to prepare inference config from current inputs:",
        error,
      );
      return inferenceConfig;
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
            setIsInferring(false);
            if (!terminalLoggedRef.current && appendWorkflowEvent) {
              terminalLoggedRef.current = true;
              const succeeded = status.exitCode === 0;
              await appendWorkflowEvent({
                actor: "system",
                event_type: succeeded
                  ? "inference.completed"
                  : "inference.failed",
                stage: "inference",
                summary: succeeded
                  ? "Inference completed successfully."
                  : "Inference finished without a successful exit.",
                payload: {
                  exitCode: status.exitCode,
                  phase: status.phase,
                  lastError: status.lastError,
                  outputPath: getPath(inference.outputPath),
                },
              });
            }
            if (status.exitCode === 0) {
              setInferenceStatus("Inference completed successfully! ✓");
            } else if (
              status.exitCode !== null &&
              status.exitCode !== undefined
            ) {
              setInferenceStatus(
                `Inference finished with exit code: ${status.exitCode}`,
              );
            } else if (status.phase === "failed" && status.lastError) {
              setInferenceStatus(`Inference failed: ${status.lastError}`);
            } else {
              setInferenceStatus("Inference stopped.");
            }
          }
        } catch (error) {
          console.error("Error polling inference status:", error);
          setIsInferring(false);
          if (!terminalLoggedRef.current && appendWorkflowEvent) {
            terminalLoggedRef.current = true;
            await appendWorkflowEvent({
              actor: "system",
              event_type: "inference.failed",
              stage: "inference",
              summary: "Inference status polling failed.",
              payload: {
                error: error.message || "unknown error",
                outputPath: getPath(inference.outputPath),
              },
            });
          }
          setInferenceStatus(
            `Inference status polling failed: ${error.message || "unknown error"}`,
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
  }, [isInferring, setIsInferring, appendWorkflowEvent, inference.outputPath]);

  const handleStartButton = async () => {
    let checkpointPath = "";
    try {
      const inferenceConfig = context.inferenceConfig;
      if (!inferenceConfig) {
        setInferenceStatus(
          "Error: Please load or upload an inference configuration first.",
        );
        return;
      }

      checkpointPath = getPath(inference.checkpointPath);
      if (!checkpointPath) {
        setInferenceStatus("Error: Please set checkpoint path first.");
        return;
      }

      setIsInferring(true);
      setInferenceStatus("Starting inference...");
      terminalLoggedRef.current = false;

      const preparedInferenceConfig =
        getPreparedInferenceConfig(inferenceConfig);

      const res = await startModelInference(
        preparedInferenceConfig,
        getPath(inference.outputPath),
        checkpointPath,
        getConfigOriginPath(),
        workflowId,
      );
      console.log(res);
      await refreshInferenceLogs();
      setInferenceStatus("Inference started. Monitoring process...");
    } catch (e) {
      console.log(e);
      setIsInferring(false);
      if (!terminalLoggedRef.current && appendWorkflowEvent) {
        terminalLoggedRef.current = true;
        await appendWorkflowEvent({
          actor: "system",
          event_type: "inference.failed",
          stage: "inference",
          summary: "Inference failed to start.",
          payload: {
            error: e.message || "unknown error",
            outputPath: getPath(inference.outputPath),
            checkpointPath,
          },
        });
      }
      await refreshInferenceLogs();
      setInferenceStatus(
        `Inference error: ${e.message || "Please check console for details."}`,
      );
    }
  };

  const handleStopButton = async () => {
    try {
      setInferenceStatus("Stopping inference...");
      await stopModelInference();
    } catch (e) {
      console.log(e);
      setInferenceStatus(
        `Error stopping inference: ${e.message || "Please check console for details."}`,
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
        <Configurator fileList={context.files} type="inference" />
        <Space wrap style={{ marginTop: 12 }} size={componentSize}>
          <Button
            onClick={handleStartButton}
            disabled={isInferring} // Disables the button when inference is running
            style={{ marginRight: "8px" }}
          >
            Start Inference
          </Button>
          <Button
            onClick={handleStopButton}
            disabled={!isInferring} // Disables the button when inference is not running
          >
            Stop Inference
          </Button>
        </Space>
        <p style={{ marginTop: 4 }}>{inferenceStatus}</p>
        <RuntimeLogPanel
          title="Inference Runtime Log"
          runtime={inferenceRuntime}
          onRefresh={refreshInferenceLogs}
        />
      </div>
    </>
  );
}

export default ModelInference;
