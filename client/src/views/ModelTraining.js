//  global localStorage
import React, { useContext, useState, useEffect, useRef } from "react";
import { Button, Space } from "antd";
import yaml from "js-yaml";
import {
  getTrainingLogs,
  startModelTraining,
  stopModelTraining,
  getTrainingStatus,
} from "../api";
import Configurator from "../components/Configurator";
import { applyInputPaths } from "../configSchema";
import RuntimeLogPanel from "../components/RuntimeLogPanel";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";

function ModelTraining() {
  const context = useContext(AppContext);
  const workflowContext = useWorkflow();
  const training = context.trainingState;
  const [isTraining, setIsTraining] = useState(false);
  const [trainingStatus, setTrainingStatus] = useState("");
  const [trainingRuntime, setTrainingRuntime] = useState(null);
  const pollingIntervalRef = useRef(null);

  const getPath = (val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.path || val.originFileObj?.path || "";
  };

  const getConfigOriginPath = () => {
    return (
      training.configOriginPath ||
      training.selectedYamlPreset ||
      getPath(training.uploadedYamlFile)
    );
  };

  const refreshTrainingLogs = async () => {
    try {
      const runtime = await getTrainingLogs();
      setTrainingRuntime(runtime);
      return runtime;
    } catch (error) {
      console.error("Error loading training logs:", error);
      return null;
    }
  };

  const refreshTrainingRuntime = async () => {
    const [status, runtime] = await Promise.all([
      getTrainingStatus(),
      getTrainingLogs(),
    ]);
    setTrainingRuntime(runtime);
    console.log("Training status:", status);

    if (!status.isRunning) {
      console.log("Training completed!");
      setIsTraining(false);

      if (status.exitCode === 0) {
        setTrainingStatus("Training completed successfully! ✓");
      } else if (status.exitCode !== null) {
        setTrainingStatus(`Training finished with exit code: ${status.exitCode}`);
      } else if (status.phase === "failed" && status.lastError) {
        setTrainingStatus(`Training failed: ${status.lastError}`);
      } else {
        setTrainingStatus("Training stopped.");
      }

      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }
  };

  const getPreparedTrainingConfig = (trainingConfig) => {
    try {
      const yamlData = yaml.load(trainingConfig);
      if (!yamlData || typeof yamlData !== "object") {
        return trainingConfig;
      }

      applyInputPaths(yamlData, {
        mode: "training",
        inputImagePath: getPath(training.inputImage),
        inputLabelPath: getPath(training.inputLabel),
        inputPath: "",
        outputPath: getPath(training.outputPath),
      });
      return yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
    } catch (error) {
      console.warn("Failed to prepare training config from current inputs:", error);
      return trainingConfig;
    }
  };

  useEffect(() => {
    refreshTrainingLogs();
  }, []);

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
  }, [isTraining]);

  const handleStartButton = async () => {
    try {
      const trainingConfig = context.trainingConfig;

      // Accept either uploaded YAML or preset-backed config text.
      if (!trainingConfig) {
        setTrainingStatus(
          "Error: Please load a preset or upload a YAML configuration first.",
        );
        return;
      }

      if (!training.outputPath) {
        setTrainingStatus("Error: Please set output path first in Step 1.");
        return;
      }

      console.log(training.uploadedYamlFile);
      console.log(trainingConfig);

      setIsTraining(true);
      setTrainingStatus(
        "Starting training... Please wait, this may take a while.",
      );

      const preparedTrainingConfig = getPreparedTrainingConfig(trainingConfig);

      // TODO: The API call should be non-blocking and return immediately
      // Real training status should be polled separately
      const res = await startModelTraining(
        preparedTrainingConfig,
        getPath(training.logPath) || getPath(training.outputPath),
        getPath(training.outputPath),
        getConfigOriginPath(),
        workflowContext?.workflow?.id,
      );
      console.log(res);
      await refreshTrainingLogs();

      // TODO: Don't set training complete here - implement proper status polling
      setTrainingStatus(
        "Training started successfully. Monitoring progress...",
      );
    } catch (e) {
      console.error("Training start error:", e);
      await refreshTrainingLogs();
      setTrainingStatus(
        `Training error: ${e.message || "Please check console for details."}`,
      );
      setIsTraining(false);
    }
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
