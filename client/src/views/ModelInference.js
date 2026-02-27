import React, { useContext, useState } from "react";
import { Button, Space } from "antd";
import { startModelInference, stopModelInference } from "../api";
import Configurator from "../components/Configurator";
import { AppContext } from "../contexts/GlobalContext";

function ModelInference({ isInferring, setIsInferring }) {
  const context = useContext(AppContext);
  // const [isInference, setIsInference] = useState(false)
  const handleStartButton = async () => {
    try {
      setIsInferring(true);
      const inferenceConfig = context.inferenceConfig;

      const getPath = (val) => {
        if (!val) return "";
        if (typeof val === "string") return val;
        return val.path || "";
      };

      const res = await startModelInference(
        inferenceConfig,
        getPath(context.outputPath),
        getPath(context.checkpointPath),
      );
      console.log(res);
    } catch (e) {
      console.log(e);
      setIsInferring(false);
    }
  };

  const handleStopButton = async () => {
    try {
      await stopModelInference();
    } catch (e) {
      console.log(e);
    } finally {
      setIsInferring(false);
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
      </div>
    </>
  );
}

export default ModelInference;
