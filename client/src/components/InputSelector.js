import { Form, Input, Select } from "antd";
import React, { useContext } from "react";
import { AppContext } from "../contexts/GlobalContext";
import { YamlContext } from "../contexts/YamlContext";

function InputSelector(props) {
  const context = useContext(AppContext);
  const YAMLContext = useContext(YamlContext);
  const { fileList, type } = props;
  console.log(fileList, context.files);

  const handleLogPathChange = (e) => {
    context.setLogPath(e.target.value);
  };

  const handleOutputPathChange = (e) => {
    context.setOutputPath(e.target.value);
  };

  const handleCheckpointPathChange = (e) => {
    context.setCheckpointPath(e.target.value);
  };

  const handleImageChange = (value) => {
    console.log(`selected ${value}`);
    context.setInputImage(context.files.find((file) => file.uid === value));
  };

  const handleLabelChange = (value) => {
    console.log(`selected ${value}`);
    context.setInputLabel(context.files.find((file) => file.uid === value));
  };

  return (
    <div>
      <Form
        labelCol={{
          span: 4,
        }}
        wrapperCol={{
          span: 14,
        }}
        layout="horizontal"
        style={{
          maxWidth: 600,
        }}
      >
        <Form.Item label="Input Image">
          <Select
            // mode="multiple"
            allowClear
            style={{
              width: "100%",
            }}
            placeholder="Please select"
            onChange={handleImageChange}
            options={context.fileList}
            size="middle"
          />
        </Form.Item>
        <Form.Item label="Input Label">
          <Select
            // mode="multiple"
            allowClear
            style={{
              width: "100%",
            }}
            placeholder="Please select"
            onChange={handleLabelChange}
            options={context.fileList}
            size="middle"
          />
        </Form.Item>
        <Form.Item label="Output Path">
          <Input
            style={{
              width: "100%",
            }}
            placeholder="Please type output path"
            onChange={handleOutputPathChange}
            size="middle"
          />
        </Form.Item>
        {type == "training" ? (
          <Form.Item label="Log Path">
            <Input
              style={{
                width: "100%",
              }}
              placeholder="Please type training log path"
              onChange={handleLogPathChange}
              size="middle"
            />
          </Form.Item>
        ) : (
          <Form.Item label="Checkpoint Path">
            <Input
              style={{
                width: "100%",
              }}
              placeholder="Please type checkpoint path"
              onChange={handleCheckpointPathChange}
              size="middle"
            />
          </Form.Item>
        )}
      </Form>
    </div>
  );
}
export default InputSelector;
