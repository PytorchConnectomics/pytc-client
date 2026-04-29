import React, { useMemo } from "react";
import { Card, Form, Input, Button, Modal, Space, Typography, Tag } from "antd";
import { FolderOpenOutlined, UploadOutlined } from "@ant-design/icons";
import UnifiedFileInput from "../../components/UnifiedFileInput";

const { Title, Text } = Typography;

/**
 * Dataset Loader Component
 * Interface for loading image datasets
 */
function DatasetLoader({ onLoad, loading, workflow }) {
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

  const basename = (value) => {
    if (!value) return "";
    const trimmed = String(value).replace(/\/+$/, "");
    return trimmed.split("/").pop() || trimmed;
  };

  const currentPair = useMemo(() => {
    if (!workflow) return null;
    const imagePath =
      workflow.image_path ||
      workflow.dataset_path ||
      workflow.inference_output_path ||
      "";
    const maskPath =
      workflow.mask_path ||
      workflow.corrected_mask_path ||
      workflow.label_path ||
      "";

    if (!imagePath) return null;
    return {
      imagePath,
      maskPath,
      projectName:
        workflow.project_name ||
        workflow.metadata?.project_name ||
        workflow.metadata?.projectName ||
        workflow.title ||
        "Proofreading review",
    };
  }, [workflow]);

  const fillCurrentPair = () => {
    if (!currentPair) return;
    form.setFieldsValue({
      projectName: currentPair.projectName,
      datasetPath: {
        path: currentPair.imagePath,
        display: basename(currentPair.imagePath),
      },
      maskPath: currentPair.maskPath
        ? { path: currentPair.maskPath, display: basename(currentPair.maskPath) }
        : undefined,
    });
  };

  const startCurrentPair = () => {
    if (!currentPair || loading) return;
    form.setFieldsValue({
      projectName: currentPair.projectName,
      datasetPath: {
        path: currentPair.imagePath,
        display: basename(currentPair.imagePath),
      },
      maskPath: currentPair.maskPath
        ? { path: currentPair.maskPath, display: basename(currentPair.maskPath) }
        : undefined,
    });
    onLoad(currentPair.imagePath, currentPair.maskPath, currentPair.projectName);
  };

  return (
    <Card
      variant="borderless"
      style={{
        maxWidth: "720px",
        margin: "0 auto",
        boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
        borderRadius: 16,
      }}
    >
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space align="center">
          <FolderOpenOutlined
            style={{ color: "var(--seg-accent-primary, #3f37c9)", fontSize: 18 }}
          />
          <Title level={4} style={{ margin: 0 }}>
            What should I proofread?
          </Title>
        </Space>
      </Space>

      <div style={{ height: 16 }} />

      {currentPair && (
        <div
          style={{
            border: "1px solid #dedbfd",
            background: "#fafaff",
            borderRadius: 12,
            padding: 12,
            marginBottom: 16,
            display: "grid",
            gap: 8,
          }}
        >
          <Space size="small" wrap>
            <Tag color="blue" style={{ margin: 0 }}>
              current project
            </Tag>
            <Text strong>{currentPair.projectName}</Text>
            <Text type="secondary">
              {basename(currentPair.imagePath)}
              {currentPair.maskPath ? ` + ${basename(currentPair.maskPath)}` : ""}
            </Text>
          </Space>
          <Space size="small" wrap>
            <Button size="small" type="primary" onClick={startCurrentPair} loading={loading}>
              Start with current data
            </Button>
            <Button size="small" onClick={fillCurrentPair}>
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
