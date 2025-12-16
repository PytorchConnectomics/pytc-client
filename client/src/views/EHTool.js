import React, { useState, useEffect } from 'react';
import { Layout } from 'antd';
import { BugOutlined } from '@ant-design/icons';
import DetectionWorkflow from './ehtool/DetectionWorkflow';

const { Content } = Layout;

/**
 * EHTool Main Component
 * Error Handling Tool for detecting and classifying errors in image stacks
 */
function EHTool({ onStartProofreading, onSessionChange, refreshTrigger, savedSessionId }) {
  // Initialize with saved session if available
  const [sessionId, setSessionId] = useState(savedSessionId || null);

  // Sync prop changes if they occur (e.g. from parent state update)
  useEffect(() => {
    if (savedSessionId && savedSessionId !== sessionId) {
      setSessionId(savedSessionId);
    }
  }, [savedSessionId]);

  // Notify parent when session changes internally
  useEffect(() => {
    if (onSessionChange) {
      onSessionChange(sessionId);
    }
  }, [sessionId, onSessionChange]);

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

        <DetectionWorkflow
          sessionId={sessionId}
          setSessionId={setSessionId}
          onStartProofreading={onStartProofreading}
          refreshTrigger={refreshTrigger}
        />
      </Content>
    </Layout>
  );
}

export default EHTool;
