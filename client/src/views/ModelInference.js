import React, { useContext, useState } from "react";
import { Button, Space } from "antd";
import { startModelInference, stopModelInference } from "../utils/api";
import Configurator from "../components/Configurator";
import { AppContext } from "../contexts/GlobalContext";

function ModelInference() {
  const context = useContext(AppContext);
  const [isInference, setIsInference] = useState(false);
  const handleStartButton = async () => {
    try {
      const res = startModelInference(
        null,
        context.uploadedYamlFile.name,
        context.outputPath,
        context.checkpointPath
      ); // inputs, configurationYaml
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

  const [componentSize, setComponentSize] = useState("default");
  const onFormLayoutChange = ({ size }) => {
    setComponentSize(size);
  };

  return (
    <>
      <div>
        {/*{"ModelTraining"}*/}
        <Configurator fileList={context.files} type="inference" />
        <Space wrap style={{ marginTop: 12 }}>
          <Button
            onClick={handleStartButton}
            // disabled={!context.trainingConfig}
          >
            Start Training
          </Button>
          <Button
            onClick={handleStopButton}
            // disabled={!isTraining}
          >
            Stop Training
          </Button>
        </Space>
      </div>
    </>
  );
}

export default ModelInference;
