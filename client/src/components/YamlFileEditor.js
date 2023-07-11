import React, { useContext, useState } from "react";
import { Upload, Button, message, Input, Slider, Col, Row, InputNumber } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";

const YamlFileEditor = () => {
    const context = useContext(AppContext);
    return (
        <div>
          {context.trainingConfig && (
            <div>
              <h2>{context.uploadedYamlFile.name}</h2>
            </div>
          )}
          {context.trainingConfig && (
            <Input.TextArea
              value={context.trainingConfig}
              // onChange={this.handleTextChange}
              autoSize={{ minRows: 4, maxRows: 8 }}
            />
          )}
        </div>
      );
    };

export default YamlFileEditor;