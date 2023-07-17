import React, { useContext, useEffect, useState } from "react";
import { Upload, Button, message, Input, Slider, Col, Row, InputNumber } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";
import { YamlContext } from "../contexts/YamlContext";

{/* WORKING ON MAKING TEXT CHANGES STICK*/}
const YamlFileEditor = () => {
    const context = useContext(AppContext);
    const YAMLContext = useContext(YamlContext);
    const [yamlContent, setYamlContent] = useState("");

    const updateYamlData = (property, value) => {
      const updatedYamlData = { ...context.yamlData, [property]: value };
      const updatedYamlContent = yaml.safeDump(updatedYamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
      setYamlContent(updatedYamlContent);
      context.setTrainingConfig(updatedYamlContent);
    };
  
    const handleTextAreaChange = (event) => {
        const updatedYamlContent = event.target.value;
        setYamlContent(updatedYamlContent);
        context.setTrainingConfig(updatedYamlContent);
        try {
          const yamlData = yaml.safeLoad(updatedYamlContent);
          YAMLContext.setNumGPUs(yamlData.SYSTEM.NUM_GPUS);
          YAMLContext.setNumCPUs(yamlData.SYSTEM.NUM_CPUS);
          YAMLContext.setLearningRate(yamlData.SOLVER.BASE_LR);
          YAMLContext.setSamplesPerBatch(yamlData.SOLVER.SAMPLES_PER_BATCH)
          // Update specific YAML values based on the updated YAML data
          // Update other YAML values as needed
        } catch (error) {
          message.error("Error parsing YAML content.");
        }
    };
    useEffect(() => {
        setYamlContent(context.trainingConfig);
      }, [context.uploadedYamlFile, context.trainingConfig]);
    return (
        <div>
          {context.trainingConfig && (
            <div>
              <h2>{context.uploadedYamlFile.name}</h2>
            </div>
          )}
          {context.trainingConfig && (
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