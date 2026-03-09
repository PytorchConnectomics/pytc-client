import { Form, Space } from "antd";
import React, { useContext } from "react";
import { AppContext } from "../contexts/GlobalContext";
import UnifiedFileInput from "./UnifiedFileInput";
import InlineHelpChat from "./InlineHelpChat";

function InputSelector(props) {
  const context = useContext(AppContext);
  const { type } = props;

  const projectContext =
    "Biomedical image segmentation using PyTorch Connectomics.";
  const taskContext =
    type === "training"
      ? "Model training configuration — Step 1: Set Inputs."
      : "Model inference configuration — Step 1: Set Inputs.";

  const handleLogPathChange = (value) => {
    context.setLogPath(value);
  };

  const handleOutputPathChange = (value) => {
    context.setOutputPath(value);
  };

  const handleCheckpointPathChange = (value) => {
    context.setCheckpointPath(value);
  };

  const handleImageChange = (value) => {
    console.log(`selected image:`, value);
    context.setInputImage(value);
  };

  const handleLabelChange = (value) => {
    console.log(`selected label:`, value);
    context.setInputLabel(value);
  };

  // Helper to get value for UnifiedFileInput (can be object or string)
  const getValue = (val) => {
    if (!val) return "";
    return val;
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
        <Form.Item
          label={
            <Space align="center">
              <span>Input Image</span>
              <InlineHelpChat
                taskKey={type}
                label="Input Image"
                yamlKey="DATASET.INPUT_PATH"
                value={context.inputImage}
                projectContext={projectContext}
                taskContext={taskContext}
              />
            </Space>
          }
        >
          <UnifiedFileInput
            placeholder="Please select or input image path"
            onChange={handleImageChange}
            value={getValue(context.inputImage)}
            selectionType={
              type === "training" || type === "inference"
                ? "fileOrDirectory"
                : "file"
            }
          />
        </Form.Item>
        <Form.Item
          label={
            <Space align="center">
              <span>Input Label</span>
              <InlineHelpChat
                taskKey={type}
                label="Input Label"
                yamlKey="DATASET.LABEL_NAME"
                value={context.inputLabel}
                projectContext={projectContext}
                taskContext={taskContext}
              />
            </Space>
          }
        >
          <UnifiedFileInput
            placeholder="Please select or input label path"
            onChange={handleLabelChange}
            value={getValue(context.inputLabel)}
            selectionType={
              type === "training" || type === "inference"
                ? "fileOrDirectory"
                : "file"
            }
          />
        </Form.Item>
        {type === "training" ? (
          <Form.Item
            label={
              <Space align="center">
                <span>Output Path</span>
                <InlineHelpChat
                  taskKey={type}
                  label="Output Path"
                  yamlKey="DATASET.OUTPUT_PATH"
                  value={context.outputPath}
                  projectContext={projectContext}
                  taskContext={taskContext}
                />
              </Space>
            }
          >
            <UnifiedFileInput
              placeholder="Directory for outputs (e.g., /path/to/outputs/)"
              value={context.outputPath || ""}
              onChange={handleOutputPathChange}
              selectionType="directory"
            />
          </Form.Item>
        ) : (
          <Form.Item
            label={
              <Space align="center">
                <span>Output Path</span>
                <InlineHelpChat
                  taskKey={type}
                  label="Output Path"
                  yamlKey="INFERENCE.OUTPUT_PATH"
                  value={context.outputPath}
                  projectContext={projectContext}
                  taskContext={taskContext}
                />
              </Space>
            }
            help="Directory where inference results will be saved"
          >
            <UnifiedFileInput
              placeholder="Directory for results (e.g., /path/to/inference_output/)"
              value={context.outputPath || ""}
              onChange={handleOutputPathChange}
              selectionType="directory"
            />
          </Form.Item>
        )}
        {type === "training" ? (
          <Form.Item
            label={
              <Space align="center">
                <span>Log Path</span>
                <InlineHelpChat
                  taskKey={type}
                  label="Log Path"
                  yamlKey="SOLVER.LOG_DIR"
                  value={context.logPath}
                  projectContext={projectContext}
                  taskContext={taskContext}
                />
              </Space>
            }
          >
            <UnifiedFileInput
              placeholder="Please type training log path"
              value={context.logPath || ""}
              onChange={handleLogPathChange}
              selectionType="directory"
            />
          </Form.Item>
        ) : (
          <Form.Item
            label={
              <Space align="center">
                <span>Checkpoint Path</span>
                <InlineHelpChat
                  taskKey={type}
                  label="Checkpoint Path"
                  yamlKey="MODEL.PRE_MODEL"
                  value={context.checkpointPath}
                  projectContext={projectContext}
                  taskContext={taskContext}
                />
              </Space>
            }
            help="Path to trained model file (.pth.tar)"
          >
            <UnifiedFileInput
              placeholder="Model checkpoint file (e.g., /path/to/checkpoint_00010.pth.tar)"
              value={context.checkpointPath || ""}
              onChange={handleCheckpointPathChange}
              selectionType="file"
            />
          </Form.Item>
        )}
      </Form>
    </div>
  );
}
export default InputSelector;
