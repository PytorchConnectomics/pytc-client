import React, { useState } from 'react';
import { Card, Form, Input, Button, message } from 'antd';
import { FolderOpenOutlined, UploadOutlined } from '@ant-design/icons';
import UnifiedFileInput from '../../components/UnifiedFileInput';

/**
 * Dataset Loader Component
 * Interface for loading image datasets
 */
function DatasetLoader({ onLoad, loading }) {
  const [form] = Form.useForm();

  const handleSubmit = (values) => {
    const datasetPath = typeof values.datasetPath === 'object' ? values.datasetPath.path : values.datasetPath;
    const maskPath = typeof values.maskPath === 'object' ? values.maskPath.path : values.maskPath;

    if (!datasetPath) {
      message.error('Please provide a dataset path');
      return;
    }

    onLoad(datasetPath, maskPath, values.projectName || 'Untitled Project');
  };

  return (
    <Card
      title={
        <span>
          <FolderOpenOutlined style={{ marginRight: '8px' }} />
          Load Dataset
        </span>
      }
      style={{ maxWidth: '600px', margin: '0 auto' }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          projectName: 'My Project'
        }}
      >
        <Form.Item
          label="Project Name"
          name="projectName"
          rules={[{ required: true, message: 'Please enter a project name' }]}
        >
          <Input placeholder="Enter project name" />
        </Form.Item>

        <Form.Item
          label="Dataset Path"
          name="datasetPath"
          rules={[{ required: true, message: 'Please enter dataset path' }]}
          help="Path to image file, directory, or glob pattern (e.g., /path/to/images/*.tif)"
        >
          <UnifiedFileInput placeholder="/path/to/dataset" />
        </Form.Item>

        <Form.Item
          label="Mask Path (Optional)"
          name="maskPath"
          help="Path to mask file or directory (optional)"
        >
          <UnifiedFileInput placeholder="/path/to/masks" />
        </Form.Item>

        <Form.Item>
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

      <div style={{
        marginTop: '24px',
        padding: '16px',
        background: '#f5f5f5',
        borderRadius: '4px'
      }}>
        <h4 style={{ marginTop: 0 }}>Supported Formats:</h4>
        <ul style={{ marginBottom: 0 }}>
          <li>Single TIFF file (2D or 3D stack)</li>
          <li>Directory of images (PNG, JPG, TIFF)</li>
          <li>Glob pattern (e.g., *.tif)</li>
        </ul>
      </div>
    </Card>
  );
}

export default DatasetLoader;
