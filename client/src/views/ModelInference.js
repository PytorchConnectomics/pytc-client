// global localStorage
import React, { useContext, useState } from "react";
import { Button, Space } from "antd";
import { startModelInference, stopModelInference } from "../utils/api";
import Configurator from "../components/Configurator";
import { AppContext } from "../contexts/GlobalContext";
import InlineHelpChat from "../components/InlineHelpChat";

function ModelInference({ isInferring, setIsInferring }) {
  const context = useContext(AppContext);
  // const [isInference, setIsInference] = useState(false)
  const handleStartButton = async () => {
    try {
      const inferenceConfig = localStorage.getItem("inferenceConfig");

      const getPath = (val) => {
        if (!val) return "";
        if (typeof val === "string") return val;
        return val.path || "";
      };

      // const res = startModelInference(
      const res = await startModelInference(
        context.uploadedYamlFile.name,
        inferenceConfig,
        getPath(context.outputPath),
        getPath(context.checkpointPath),
      ); // inputs, configurationYaml
      console.log(res);
    } catch (e) {
      console.log(e);
    } finally {
      // setIsInference(true)
      setIsInferring(true);
    }
  };

  const handleStopButton = async () => {
    try {
      await stopModelInference();
    } catch (e) {
      console.log(e);
    } finally {
      // setIsInference(false)
      setIsInferring(false);
    }
  };

  // const [componentSize, setComponentSize] = useState("default");
  const [componentSize] = useState("default");
  // const onFormLayoutChange = ({ size }) => {
  //   setComponentSize(size);
  // };

  return (
    <>
      <div>
        <Configurator fileList={context.files} type="inference" />
        <Space wrap style={{ marginTop: 12 }} size={componentSize}>
          <Space align="center">
            <Button
              onClick={handleStartButton}
              disabled={isInferring} // Disables the button when inference is running
            >
              Start Inference
            </Button>
            <InlineHelpChat
              taskKey="inference"
              label="Start Inference"
              yamlKey="INFERENCE.START"
              value={null}
              projectContext="Mitochondria segmentation on an electron microscopy volume."
              taskContext="Model inference configuration and execution in PyTorch Connectomics."
            />
          </Space>
          <Space align="center">
            <Button
              onClick={handleStopButton}
              disabled={!isInferring} // Disables the button when inference is not running
            >
              Stop Inference
            </Button>
            <InlineHelpChat
              taskKey="inference"
              label="Stop Inference"
              yamlKey="INFERENCE.STOP"
              value={null}
              projectContext="Mitochondria segmentation on an electron microscopy volume."
              taskContext="Model inference configuration and execution in PyTorch Connectomics."
            />
          </Space>
        </Space>
      </div>
    </>
  );
}

export default ModelInference;
