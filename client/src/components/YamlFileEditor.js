import React, { useContext, useEffect, useState } from "react";
import { Input, message, Space } from "antd";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";
import InlineHelpChat from "./InlineHelpChat";

const YamlFileEditor = (props) => {
  const context = useContext(AppContext);
  const [yamlContent, setYamlContent] = useState("");
  const { type } = props;
  const projectContext =
    "Mitochondria segmentation on an electron microscopy volume.";
  const taskContext =
    type === "training"
      ? "Model training configuration in PyTorch Connectomics."
      : "Model inference configuration in PyTorch Connectomics.";

  const handleTextAreaChange = (event) => {
    const updatedYamlContent = event.target.value;
    setYamlContent(updatedYamlContent);
    if (type === "training") {
      context.setTrainingConfig(updatedYamlContent);
    } else {
      context.setInferenceConfig(updatedYamlContent);
    }
    try {
      // const yamlData = yaml.load(updatedYamlContent);
      yaml.load(updatedYamlContent);

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
    }

    if (type === "inference") {
      setYamlContent(context.inferenceConfig);
    }
  }, [
    context.uploadedYamlFile,
    context.trainingConfig,
    context.inferenceConfig,
    type,
  ]);

  return (
    <div>
      {yamlContent && (
        <div>
          <Space align="center">
            <h2 style={{ marginBottom: 0 }}>{context.uploadedYamlFile.name}</h2>
            <InlineHelpChat
              taskKey={type}
              label="YAML editor"
              yamlKey="CONFIG.YAML"
              value={null}
              projectContext={projectContext}
              taskContext={taskContext}
            />
          </Space>
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
