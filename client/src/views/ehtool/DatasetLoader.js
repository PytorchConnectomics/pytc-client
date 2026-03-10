import React from "react";
import { Card, Form, Input, Button, Modal, Space, Typography } from "antd";
import { FolderOpenOutlined, UploadOutlined } from "@ant-design/icons";
import UnifiedFileInput from "../../components/UnifiedFileInput";

const { Title, Text } = Typography;

/**
 * Dataset Loader Component
 * Interface for loading image datasets
 */
function DatasetLoader({ onLoad, loading }) {
  const [form] = Form.useForm();

  const resolvePath = (value) => {
    if (!value) return "";
    if (typeof value === "string") return value.trim();
    return (value.path || value.folderPath || "").trim();
  };

  const showValidationError = (title, description) => {
    Modal.error({
      title,
      content: description,
      okText: "Got it",
    });
  };

  const handleSubmit = async (values) => {
    const datasetPath = resolvePath(values.datasetPath);
    const maskPath = resolvePath(values.maskPath);
    const projectName = (values.projectName || "").trim();

    if (!projectName) {
      showValidationError(
        "Project name required",
        "Please provide a name for this proofreading session.",
      );
      return;
    }

    if (!datasetPath) {
      showValidationError(
        "Dataset path required",
        "Select a dataset file/folder before starting the session.",
      );
      return;
    }

    if (datasetPath.includes("..") || maskPath.includes("..")) {
      showValidationError(
        "Invalid path",
        "Paths containing '..' are not allowed. Please pick a direct file/folder path.",
      );
      return;
    }

    try {
      await onLoad(datasetPath, maskPath, projectName || "Untitled Project");
    } catch (error) {
      showValidationError(
        "Failed to load dataset",
        "Unable to start proofreading with the provided paths. Check the selected files and try again.",
      );
    }
  };

  return (
    <Card
      bordered={false}
      style={{
        maxWidth: "720px",
        margin: "0 auto",
        boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
        borderRadius: 16,
      }}
    >
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space align="center">
          <FolderOpenOutlined style={{ color: "#1677ff", fontSize: 18 }} />
          <Title level={4} style={{ margin: 0 }}>
            Start a Mask Proofreading Session
          </Title>
        </Space>
        <Text type="secondary">
          Load a volume (single file, folder, or glob). Add a mask if you have
          one.
        </Text>
      </Space>

      <div style={{ height: 16 }} />

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          projectName: "My Project",
        }}
      >
        <Form.Item
          label="Project Name"
          name="projectName"
          rules={[{ required: true, message: "Please enter a project name" }]}
        >
          <Input placeholder="My EM volume" />
        </Form.Item>

        <Form.Item
          label="Dataset Path"
          name="datasetPath"
          rules={[{ required: true, message: "Please enter dataset path" }]}
        >
          <UnifiedFileInput placeholder="/path/to/dataset" />
        </Form.Item>

        <Form.Item label="Mask Path (Optional)" name="maskPath">
          <UnifiedFileInput placeholder="/path/to/masks" />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            icon={<UploadOutlined />}
            block
            size="large"
          >
            Load Dataset
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

export default DatasetLoader;
