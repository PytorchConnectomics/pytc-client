import React, { useEffect, useState } from "react";
import { Card, Form, Input, Button, Modal, Space, Typography, Tag } from "antd";
import { FolderOpenOutlined, UploadOutlined } from "@ant-design/icons";
import UnifiedFileInput from "../../components/UnifiedFileInput";
import { apiClient } from "../../api";

const { Title, Text } = Typography;

/**
 * Dataset Loader Component
 * Interface for loading image datasets
 */
function DatasetLoader({ onLoad, loading }) {
  const [form] = Form.useForm();
  const [projectSuggestions, setProjectSuggestions] = useState([]);

  useEffect(() => {
    let active = true;
    apiClient
      .get("/files/project-suggestions")
      .then((response) => {
        if (active) setProjectSuggestions(response.data || []);
      })
      .catch(() => {
        if (active) setProjectSuggestions([]);
      });
    return () => {
      active = false;
    };
  }, []);

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

  const joinPath = (root, relative) => {
    if (!root || !relative) return "";
    return `${String(root).replace(/\/+$/, "")}/${String(relative).replace(/^\/+/, "")}`;
  };

  const suggestedProject =
    projectSuggestions.find((item) => item.recommended) || projectSuggestions[0];
  const suggestedPair = suggestedProject?.profile?.paired_examples?.[0];

  const fillSuggestedPair = () => {
    if (!suggestedProject || !suggestedPair) return;
    const imagePath = joinPath(suggestedProject.directory_path, suggestedPair.image);
    const maskPath = joinPath(suggestedProject.directory_path, suggestedPair.label);
    form.setFieldsValue({
      projectName: suggestedProject.name,
      datasetPath: { path: imagePath, display: suggestedPair.image },
      maskPath: { path: maskPath, display: suggestedPair.label },
    });
  };

  const startSuggestedPair = () => {
    if (!suggestedProject || !suggestedPair || loading) return;
    const imagePath = joinPath(suggestedProject.directory_path, suggestedPair.image);
    const maskPath = joinPath(suggestedProject.directory_path, suggestedPair.label);
    form.setFieldsValue({
      projectName: suggestedProject.name,
      datasetPath: { path: imagePath, display: suggestedPair.image },
      maskPath: { path: maskPath, display: suggestedPair.label },
    });
    onLoad(imagePath, maskPath, suggestedProject.name);
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
            What should I proofread?
          </Title>
        </Space>
      </Space>

      <div style={{ height: 16 }} />

      {suggestedProject && suggestedPair && (
        <div
          style={{
            border: "1px solid #d9f7be",
            background: "#fbfff7",
            borderRadius: 12,
            padding: 12,
            marginBottom: 16,
            display: "grid",
            gap: 8,
          }}
        >
          <Space size="small" wrap>
            <Tag color="green" style={{ margin: 0 }}>
              suggested
            </Tag>
            <Text strong>{suggestedProject.name}</Text>
          </Space>
          <Space size="small" wrap>
            <Button size="small" type="primary" onClick={startSuggestedPair} loading={loading}>
              Start proofreading this pair
            </Button>
            <Button size="small" onClick={fillSuggestedPair}>
              Fill form
            </Button>
          </Space>
        </div>
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          projectName: "My Project",
        }}
      >
        <Form.Item
          label="Review name"
          name="projectName"
          rules={[{ required: true, message: "Name this review" }]}
        >
          <Input placeholder="My EM volume" />
        </Form.Item>

        <Form.Item
          label="Image to proofread"
          name="datasetPath"
          rules={[{ required: true, message: "Choose the image volume" }]}
        >
          <UnifiedFileInput
            placeholder="/path/to/image"
            selectionType="fileOrDirectory"
          />
        </Form.Item>

        <Form.Item label="Mask to edit (optional)" name="maskPath">
          <UnifiedFileInput
            placeholder="/path/to/mask"
            selectionType="fileOrDirectory"
          />
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
            Start proofreading
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

export default DatasetLoader;
