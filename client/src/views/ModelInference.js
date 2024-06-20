import React, { useContext, useState } from "react";
import { Button, Space } from "antd";
import { startModelInference, stopModelInference } from "../utils/api";
import Configurator from "../components/Configurator";
import { AppContext } from "../contexts/GlobalContext";

function ModelInference() {
  const context = useContext(AppContext);
  const [, setIsInference] = useState(false);
  const handleStartButton = async () => {
    try {
      const inferenceConfig = localStorage.getItem("inferenceConfig");

      const res = startModelInference(
        context.uploadedYamlFile.name,
        inferenceConfig,
        context.outputPath,
        context.checkpointPath
      ); 
      console.log(res);
    } catch (e) {
      console.log(e);
    } finally {
      setIsInference(true);
    }
  };

  const handleStopButton = async () => {
    try {
      stopModelInference();
    } catch (e) {
      console.log(e);
    } finally {
      setIsInference(false);
    }
  };


  return (
    <>
      <div>
        <Configurator fileList={context.files} type="inference" />
        <Space wrap style={{ marginTop: 12 }}>
          <Button
            onClick={handleStartButton}
          >
            Start Inference
          </Button>
          <Button
            onClick={handleStopButton}
          >
            Stop Inference
          </Button>
        </Space>
      </div>
    </>
  );
}

export default ModelInference;
