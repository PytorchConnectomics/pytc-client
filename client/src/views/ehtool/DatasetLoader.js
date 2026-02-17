import React from "react";
import { Card, Form, Input, Button, message, Space, Typography } from "antd";
import { FolderOpenOutlined, UploadOutlined } from "@ant-design/icons";
import UnifiedFileInput from "../../components/UnifiedFileInput";

const { Title, Text } = Typography;

/**
 * Dataset Loader Component
 * Interface for loading image datasets
 */
function DatasetLoader({ onLoad, loading }) {
  const [form] = Form.useForm();

  const handleSubmit = (values) => {
    const datasetPath =
      typeof values.datasetPath === "object"
        ? values.datasetPath.path
        : values.datasetPath;
    const maskPath =
      typeof values.maskPath === "object"
        ? values.maskPath.path
        : values.maskPath;

    if (!datasetPath) {
      message.error("Please provide a dataset path");
      return;
    }

    onLoad(datasetPath, maskPath, values.projectName || "Untitled Project");
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
          help="File, directory, or glob (e.g., /path/to/images/*.tif)"
        >
          <UnifiedFileInput placeholder="/path/to/dataset" />
        </Form.Item>

        <Form.Item
          label="Mask Path (Optional)"
          name="maskPath"
          help="Mask file or directory (optional)"
        >
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

      <div style={{ marginTop: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Supported: single TIFF (2D/3D), image folders (PNG/JPG/TIFF), or glob
          patterns like `*.tif`.
        </Text>
      </div>
    </Card>
  );
}

export default DatasetLoader;
