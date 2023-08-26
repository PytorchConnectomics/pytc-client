import React, { useContext, useEffect, useState } from "react";
import { Input, message } from "antd";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";
import { YamlContext } from "../contexts/YamlContext";

const YamlFileEditor = (props) => {
  const context = useContext(AppContext);
  const YAMLContext = useContext(YamlContext);
  const [yamlContent, setYamlContent] = useState("");

  const { type } = props;

  const handleTextAreaChange = (event) => {
    const updatedYamlContent = event.target.value;
    setYamlContent(updatedYamlContent);
    context.setTrainingConfig(updatedYamlContent);
    try {
      const yamlData = yaml.safeLoad(updatedYamlContent);

      // YAMLContext.setNumGPUs(yamlData.SYSTEM.NUM_GPUS);
      // YAMLContext.setNumCPUs(yamlData.SYSTEM.NUM_CPUS);
      // YAMLContext.setLearningRate(yamlData.SOLVER.BASE_LR);
      // YAMLContext.setSamplesPerBatch(yamlData.SOLVER.SAMPLES_PER_BATCH);
    } catch (error) {
      message.error("Error parsing YAML content.");
    }
  };
  useEffect(() => {
    if (type === "training") {
      setYamlContent(context.trainingConfig);
    } else {
      setYamlContent(context.inferenceConfig);
    }
  }, [
    context.uploadedYamlFile,
    context.trainingConfig,
    context.inferenceConfig,
  ]);

  return (
    <div>
      {yamlContent && (
        <div>
          <h2>{context.uploadedYamlFile.name}</h2>
        </div>
      )}
      {yamlContent && (
        <Input.TextArea
          value={yamlContent}
          onChange={handleTextAreaChange}
          autoSize={{ minRows: 4, maxRows: 8 }}
        />
      )}
    </div>
  );
};
export default YamlFileEditor;
