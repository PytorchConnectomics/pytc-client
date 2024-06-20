import { Form, Input, Select } from "antd";
import React, { useContext } from "react";
import { AppContext } from "../contexts/GlobalContext";

function InputSelector(props) {
  const context = useContext(AppContext);
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
    <div style={{ marginTop: "10px" }}>
      <Form
        labelCol={{
          span: 5,
        }}
        wrapperCol={{
          span: 14,
        }}
      >
        <Form.Item label="Input Image">
          <Select
            allowClear
            style={{ width: "100%" }}
            placeholder="Please select"
            onChange={handleImageChange}
            value={context.inputImage ? context.inputImage.uid : undefined}
            options={context.imageFileList.map((file) => ({
              label: file.name,
              value: file.uid,
            }))}
            size="middle"
          />
        </Form.Item>
        <Form.Item label="Input Label">
          <Select
            allowClear
            style={{ width: "100%" }}
            placeholder="Please select"
            onChange={handleLabelChange}
            value={context.inputLabel ? context.inputLabel.uid : undefined}
            options={context.labelFileList.map((file) => ({
              label: file.name,
              value: file.uid,
            }))}
            size="middle"
          />
        </Form.Item>
        {type === "training" ? <Form.Item label="Output Path">
          <Input
            style={{
              width: "100%",
            }}
            placeholder="Please type output path"
            value={context.outputPath ? context.outputPath : undefined}
            onChange={handleOutputPathChange}
            size="middle"
          />
        </Form.Item>
          : null}
        {type === "training" ? (
          <Form.Item label="Log Path">
            <Input
              style={{
                width: "100%",
              }}
              placeholder="Please type training log path"
              value={context.logPath ? context.logPath : undefined}
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
              value={context.outputPath ? context.outputPath : undefined}
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
