import React, { useState } from 'react';
import { Modal, Button, Checkbox, Space, Typography, Row, Col } from 'antd';
import {
  FolderOpenOutlined,
  BugOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
  ApartmentOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

const WorkflowSelector = ({ visible, onSelect, onCancel, isManual }) => {
  // Default to having Files selected
  const [selectedModes, setSelectedModes] = useState(['files']);
  const [remember, setRemember] = useState(false);

  const handleOk = () => {
    onSelect(selectedModes, remember);
  };

  const options = [
    { label: 'File Management', value: 'files', icon: <FolderOpenOutlined /> },
    { label: 'Visualization', value: 'visualization', icon: <EyeOutlined /> },
    { label: 'Model Training', value: 'training', icon: <ExperimentOutlined /> },
    { label: 'Model Inference', value: 'inference', icon: <ThunderboltOutlined /> },
    { label: 'Tensorboard', value: 'monitoring', icon: <DashboardOutlined /> },
    { label: 'SynAnno', value: 'synanno', icon: <ApartmentOutlined /> },
    { label: 'Worm Error Handling', value: 'worm-error-handling', icon: <BugOutlined /> }
  ];

  const onChange = (checkedValues) => {
    setSelectedModes(checkedValues);
  };

  return (
    <Modal
      title={<Title level={4}>{isManual ? 'Update Startup Preference' : 'Select Workflows'}</Title>}
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      footer={[
        <Button
          key="submit"
          type="primary"
          onClick={handleOk}
          size="large"
          block
          disabled={selectedModes.length === 0}
        >
          {isManual ? 'Save Preference' : 'Launch Selected'}
        </Button>,
      ]}
      closable={isManual} // Allow closing if manual
      maskClosable={isManual}
      centered
      width={600}
    >
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Text type="secondary">
          {isManual
            ? 'Choose the tabs you want to see automatically next time.'
            : 'Choose the tabs you want to work with in this session.'}
        </Text>
      </div>

      <Checkbox.Group
        value={selectedModes}
        onChange={onChange}
        style={{ width: '100%' }}
      >
        <Row gutter={[16, 16]}>
          {options.map(opt => (
            <Col span={12} key={opt.value}>
              <div style={{
                border: '1px solid #d9d9d9',
                borderRadius: '4px',
                padding: '12px',
                display: 'flex',
                alignItems: 'center',
                backgroundColor: selectedModes.includes(opt.value) ? '#e6f7ff' : 'transparent',
                borderColor: selectedModes.includes(opt.value) ? '#1890ff' : '#d9d9d9'
              }}>
                <Checkbox value={opt.value} style={{ width: '100%' }}>
                  <Space>
                    {opt.icon}
                    <span style={{ fontSize: 16 }}>{opt.label}</span>
                  </Space>
                </Checkbox>
              </div>
            </Col>
          ))}
        </Row>
      </Checkbox.Group>

      <div style={{ marginTop: 24, textAlign: 'center' }}>
        <Checkbox checked={remember} onChange={e => setRemember(e.target.checked)}>
          {isManual ? 'Enable auto-launch with these settings' : 'Remember my choice'}
        </Checkbox>
      </div>
    </Modal>
  );
};

export default WorkflowSelector;
