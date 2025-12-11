import React, { useState, useEffect, useMemo } from 'react';
import { Layout, Tabs, message } from 'antd';
import { BugOutlined } from '@ant-design/icons';
import DetectionWorkflow from './ehtool/DetectionWorkflow';

const { Content } = Layout;

/**
 * EHTool Main Component
 * Error Handling Tool for detecting and classifying errors in image stacks
 */
function EHTool({ onStartProofreading, onSessionChange }) {
  const [activeTab, setActiveTab] = useState('detection');
  const [sessionId, setSessionId] = useState(null);

  // Notify parent when session changes
  useEffect(() => {
    if (onSessionChange) {
      onSessionChange(sessionId);
    }
  }, [sessionId, onSessionChange]);

  // Use useMemo to prevent tabs from being recreated on every render
  const tabs = useMemo(() => [
    {
      key: 'detection',
      label: (
        <span>
          <BugOutlined />
          Error Detection
        </span>
      ),
      children: (
        <DetectionWorkflow
          sessionId={sessionId}
          setSessionId={setSessionId}
          onStartProofreading={onStartProofreading}
        />
      )
    }
  ], [sessionId, onStartProofreading]);

  return (
    <Layout style={{ height: '100%', background: '#fff' }}>
      <Content style={{ padding: '16px' }}>
        <div style={{ marginBottom: '16px' }}>
          <h2 style={{ margin: 0 }}>
            <BugOutlined style={{ marginRight: '8px' }} />
            Error Handling Tool
          </h2>
          <p style={{ color: '#666', marginTop: '4px' }}>
            Detect and classify errors in image stacks
          </p>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabs}
          size="large"
          destroyInactiveTabPane={false}
        />
      </Content>
    </Layout>
  );
}

export default EHTool;
