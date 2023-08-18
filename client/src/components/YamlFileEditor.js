import React, { useContext, useEffect, useState } from "react";
import { Input } from "antd";
import { AppContext } from "../contexts/GlobalContext";
import { YamlContext } from "../contexts/YamlContext";

const YamlFileEditor = () => {
  const context = useContext(AppContext);
  const YAMLContext = useContext(YamlContext);
  const [yamlContent, setYamlContent] = useState("");

  // const updateYamlData = (property, value) => {
  //   const updatedYamlData = { ...context.yamlData, [property]: value };
  //   const updatedYamlContent = yaml
  //     .safeDump(updatedYamlData, { indent: 2 })
  //     .replace(/^\s*\n/gm, "");
  //   setYamlContent(updatedYamlContent);
  //   context.setTrainingConfig(updatedYamlContent);
  // };

  const handleTextAreaChange = (event) => {
    const updatedYamlContent = event.target.value;
    setYamlContent(updatedYamlContent);
    context.setTrainingConfig(updatedYamlContent);
    // try {
    //   const yamlData = yaml.safeLoad(updatedYamlContent);
    //   YAMLContext.setNumGPUs(yamlData.SYSTEM.NUM_GPUS);
    //   YAMLContext.setNumCPUs(yamlData.SYSTEM.NUM_CPUS);
    //   YAMLContext.setLearningRate(yamlData.SOLVER.BASE_LR);
    //   YAMLContext.setSamplesPerBatch(yamlData.SOLVER.SAMPLES_PER_BATCH);
    // } catch (error) {
    //   message.error("Error parsing YAML content.");
    // }
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