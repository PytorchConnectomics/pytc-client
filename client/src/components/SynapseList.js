import React from 'react';
import { List, Typography, Progress } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, QuestionCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

/**
 * SynapseList Component
 * 
 * Displays a scrollable list of synapses with status indicators and progress tracking.
 * Highlights the currently selected synapse and allows clicking to navigate.
 * 
 * @param {array} synapses - Array of synapse objects
 * @param {number} currentIndex - Index of currently selected synapse
 * @param {function} onSelectSynapse - Callback when synapse is clicked
 * @param {number} reviewedCount - Number of reviewed synapses
 */
function SynapseList({ synapses, currentIndex, onSelectSynapse, reviewedCount }) {

  /**
   * Get icon based on synapse status
   */
  const getStatusIcon = (status) => {
    switch (status) {
      case 'correct':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'incorrect':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'unsure':
        return <QuestionCircleOutlined style={{ color: '#faad14' }} />;
      default:
        return null; // No icon for 'error' status
    }
  };

  // Calculate progress
  const totalErrors = synapses.filter(s => s.status === 'error').length;
  const progress = totalErrors > 0 ? (reviewedCount / totalErrors) * 100 : 0;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px' }}>
      {/* Progress Section */}
      <div style={{ marginBottom: '16px' }}>
        <Text strong style={{ display: 'block', marginBottom: '8px' }}>Progress</Text>
        <Progress
          percent={Math.round(progress)}
          status="active"
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {reviewedCount} / {totalErrors} reviewed
        </Text>
      </div>

      {/* Synapse List */}
      <List
        size="small"
        dataSource={synapses}
        style={{ flex: 1, overflow: 'auto' }}
        renderItem={(synapse, index) => (
          <List.Item
            onClick={() => onSelectSynapse(index)}
            style={{
              cursor: 'pointer',
              backgroundColor: index === currentIndex ? '#e6f7ff' : 'transparent',
              borderLeft: index === currentIndex ? '3px solid #1890ff' : '3px solid transparent',
              padding: '8px 12px',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              if (index !== currentIndex) {
                e.currentTarget.style.backgroundColor = '#f5f5f5';
              }
            }}
            onMouseLeave={(e) => {
              if (index !== currentIndex) {
                e.currentTarget.style.backgroundColor = 'transparent';
              }
            }}
          >
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <Text strong style={{ fontSize: '13px' }}>Synapse #{synapse.id}</Text>
                {getStatusIcon(synapse.status)}
              </div>
              <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>
                ({synapse.x.toFixed(1)}, {synapse.y.toFixed(1)}, {synapse.z.toFixed(1)})
              </Text>
              {synapse.confidence && (
                <Text type="secondary" style={{ fontSize: '10px', display: 'block' }}>
                  Confidence: {(synapse.confidence * 100).toFixed(0)}%
                </Text>
              )}
            </div>
          </List.Item>
        )}
      />
    </div>
  );
}

export default SynapseList;
