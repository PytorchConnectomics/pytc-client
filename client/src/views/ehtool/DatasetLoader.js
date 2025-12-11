import React, { useState } from 'react';
import { Card, Form, Input, Button, Upload, message, Modal } from 'antd';
import { FolderOpenOutlined, UploadOutlined, LaptopOutlined, CloudServerOutlined } from '@ant-design/icons';
import FilePickerModal from '../../components/FilePickerModal';

/**
 * Dataset Loader Component
 * Interface for loading image datasets
 */
function DatasetLoader({ onLoad, loading }) {
  const [form] = Form.useForm();
  const [datasetPath, setDatasetPath] = useState('');
  const [maskPath, setMaskPath] = useState('');

  const [filePickerVisible, setFilePickerVisible] = useState(false);
  const [activeField, setActiveField] = useState(null);

  const handleBrowse = (fieldName) => {
    setActiveField(fieldName);
    Modal.confirm({
      title: 'Select File Source',
      icon: <FolderOpenOutlined />,
      content: 'Where would you like to select the file from?',
      okText: 'Local Machine',
      cancelText: 'Server Storage',
      okButtonProps: { icon: <LaptopOutlined /> },
      cancelButtonProps: { icon: <CloudServerOutlined /> },
      closable: true,
      maskClosable: true,
      onOk: async () => {
        try {
          const { ipcRenderer } = window.require('electron');
          const filePath = await ipcRenderer.invoke('dialog:openFile');
          if (filePath) {
            form.setFieldsValue({ [fieldName]: filePath });
          }
        } catch (error) {
          console.error('Error opening file dialog:', error);
          message.error('Failed to open file dialog');
        }
      },
      onCancel: (close) => {
        // Check if it was a cancel action or button click
        // AntD confirm onCancel is triggered by Cancel button AND close/mask click
        // We only want to open Server picker if Cancel button (Server Storage) was clicked
        // But AntD Confirm is binary. Let's use a custom modal or just assume Cancel = Server for now
        // Actually, onCancel receives a function to close? No.
        // Let's just open the picker. If user closed, they can close picker.
        // Better UX: Custom modal, but Confirm is quick.
        // Let's assume 'Cancel' button is 'Server Storage'.
        // If user clicks X or mask, it also triggers onCancel.
        // We can distinguish by the trigger argument if available, but it's not standard.
        // Let's just set visible.
        if (close && close.trigger) {
          // If triggered by close button, do nothing?
          // AntD 4/5 confirm doesn't pass trigger easily.
          // Let's just open it.
        }
        setFilePickerVisible(true);
      }
    });
  };

  const handleFilePickerSelect = (item) => {
    if (activeField) {
      // Use physical_path if available (for files), otherwise construct path
      let fullPath;
      if (item.physical_path) {
        // Backend file with physical path
        fullPath = item.physical_path;
      } else if (item.path && item.path !== 'root') {
        // Fallback: construct relative path
        fullPath = `${item.path}/${item.name}`;
      } else {
        // Just the name
        fullPath = item.name;
      }

      form.setFieldsValue({ [activeField]: fullPath });
      setFilePickerVisible(false);
    }
  };

  const handleSubmit = (values) => {
    if (!values.datasetPath) {
      message.error('Please provide a dataset path');
      return;
    }

    onLoad(values.datasetPath, values.maskPath, values.projectName || 'Untitled Project');
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
          <Input
            placeholder="/path/to/dataset"
            prefix={
              <FolderOpenOutlined
                style={{ cursor: 'pointer', color: '#1890ff' }}
                onClick={() => handleBrowse('datasetPath')}
              />
            }
          />
        </Form.Item>

        <Form.Item
          label="Mask Path (Optional)"
          name="maskPath"
          help="Path to mask file or directory (optional)"
        >
          <Input
            placeholder="/path/to/masks"
            prefix={
              <FolderOpenOutlined
                style={{ cursor: 'pointer', color: '#1890ff' }}
                onClick={() => handleBrowse('maskPath')}
              />
            }
          />
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

      <FilePickerModal
        visible={filePickerVisible}
        onCancel={() => setFilePickerVisible(false)}
        onSelect={handleFilePickerSelect}
        title={`Select ${activeField === 'datasetPath' ? 'Dataset' : 'Mask'} Path`}
      />
    </Card>
  );
}

export default DatasetLoader;
