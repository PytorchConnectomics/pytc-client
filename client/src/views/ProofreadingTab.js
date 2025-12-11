import React from 'react';
import { Card, Button } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import ProofreadingWorkflow from './ehtool/ProofreadingWorkflow';

/**
 * Proofreading Tab Component
 * Wrapper for the proofreading workflow that can be accessed as a separate tab
 */
function ProofreadingTab({ sessionId, refreshTrigger, onComplete }) {
  console.log('[ProofreadingTab] Received sessionId:', sessionId);

  if (!sessionId) {
    return (
      <div style={{ padding: '24px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Card style={{ maxWidth: '500px', textAlign: 'center' }}>
          <h2>No Active Session</h2>
          <p style={{ color: '#666', marginBottom: '24px' }}>
            Please load a dataset in the Error Handling tab first, then classify some layers as incorrect.
          </p>
          <Button
            type="primary"
            icon={<ArrowLeftOutlined />}
            onClick={onComplete}
            size="large"
          >
            Go to Error Handling
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ height: '100%' }}>
      <ProofreadingWorkflow
        sessionId={sessionId}
        refreshTrigger={refreshTrigger}
        onComplete={onComplete}
      />
    </div>
  );
}

export default ProofreadingTab;
