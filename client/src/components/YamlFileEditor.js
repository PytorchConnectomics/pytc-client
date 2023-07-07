import React, { useContext, useEffect, useState } from "react";
import { Upload, Button, message, Input, Slider, Col, Row, InputNumber } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";

{/* WORKING ON MAKING TEXT CHANGES STICK*/}
const YamlFileEditor = () => {
    const context = useContext(AppContext);
    const [yamlContent, setYamlContent] = useState("");

    const handleTextAreaChange = (event) => {
        const updatedYamlContent = event.target.value;
        setYamlContent(updatedYamlContent);
    
     
        try {
          const updatedYamlData = yaml.safeLoad(updatedYamlContent);
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