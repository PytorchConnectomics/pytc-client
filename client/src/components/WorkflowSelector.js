import React, { useEffect, useState } from 'react';
import { Modal, Button, Checkbox, Space, Typography, Row, Col, Card } from 'antd';
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

const WorkflowSelector = ({ visible, onSelect, onCancel, isManual, initialModes }) => {
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
    { label: 'TensorBoard', value: 'monitoring', icon: <DashboardOutlined /> },
    { label: 'SynAnno', value: 'synanno', icon: <ApartmentOutlined /> },
    { label: 'Worm Error Handling', value: 'worm-error-handling', icon: <BugOutlined /> }
  ];

  useEffect(() => {
    if (visible) {
      setSelectedModes((initialModes && initialModes.length > 0) ? initialModes : ['files']);
      setRemember(false);
    }
  }, [visible, initialModes]);

  const toggleMode = (value) => {
    setSelectedModes((prev) => (
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    ));
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
      closable
      maskClosable
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

      <Row gutter={[16, 16]}>
        {options.map((opt) => {
          const isSelected = selectedModes.includes(opt.value);
          return (
            <Col span={12} key={opt.value}>
              <Card
                size="small"
                hoverable
                onClick={() => toggleMode(opt.value)}
                bodyStyle={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 12,
                }}
                style={{
                  borderColor: isSelected ? '#1677ff' : '#f0f0f0',
                  backgroundColor: isSelected ? '#f0f7ff' : '#fff',
                }}
              >
                <Checkbox
                  checked={isSelected}
                  onChange={() => toggleMode(opt.value)}
                  onClick={(e) => e.stopPropagation()}
                />
                <Space>
                  {opt.icon}
                  <span style={{ fontSize: 16 }}>{opt.label}</span>
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>

      <div style={{ marginTop: 16 }}>
        <Checkbox checked={remember} onChange={e => setRemember(e.target.checked)}>
          {isManual ? 'Enable auto-launch with these settings' : 'Remember my choice'}
        </Checkbox>
      </div>
    </Modal>
  );
};

export default WorkflowSelector;
