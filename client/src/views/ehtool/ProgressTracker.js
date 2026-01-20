import React from 'react';
import { Card, Progress, Statistic, Row, Col, Button, Divider } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, QuestionCircleOutlined, ExclamationCircleOutlined, FolderOpenOutlined, EditOutlined } from '@ant-design/icons';

/**
 * Progress Tracker Component
 * Displays statistics and progress for the detection workflow
 */
function ProgressTracker({ stats, projectName, totalLayers, onNewSession, onStartProofreading }) {
  if (!stats) {
    return (
      <div style={{ padding: '16px' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: '24px' }}>
            <p style={{ color: '#999' }}>No session loaded</p>
          </div>
        </Card>
      </div>
    );
  }

  const progressPercent = stats.progress_percent || 0;

  return (
    <div style={{ padding: '16px' }}>
      <Card
        title="Project Info"
        size="small"
        style={{ marginBottom: '16px' }}
      >
        <div style={{ marginBottom: '8px' }}>
          <strong>{projectName}</strong>
        </div>
        <div style={{ fontSize: '12px', color: '#666' }}>
          {totalLayers} layers total
        </div>
      </Card>

      <Card
        title="Progress"
        size="small"
        style={{ marginBottom: '16px' }}
      >
        <Progress
          percent={progressPercent}
          status={progressPercent === 100 ? 'success' : 'active'}
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
        <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '12px', color: '#666' }}>
          {stats.reviewed} / {stats.total} layers reviewed
        </div>
      </Card>

      <Card title="Classification Summary" size="small" style={{ marginBottom: '16px' }}>
        <Row gutter={[8, 8]}>
          <Col span={12}>
            <Statistic
              title="Correct"
              value={stats.correct}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ fontSize: '20px' }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Incorrect"
              value={stats.incorrect}
              prefix={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
              valueStyle={{ fontSize: '20px' }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Unsure"
              value={stats.unsure}
              prefix={<QuestionCircleOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ fontSize: '20px' }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Unreviewed"
              value={stats.error}
              prefix={<ExclamationCircleOutlined style={{ color: '#d9d9d9' }} />}
              valueStyle={{ fontSize: '20px' }}
            />
          </Col>
        </Row>
      </Card>

      <Divider />

      {stats && stats.incorrect > 0 && (
        <Button
          type="primary"
          icon={<EditOutlined />}
          onClick={onStartProofreading}
          block
          style={{ marginBottom: '12px' }}
        >
          Proofread Incorrect Layers ({stats.incorrect})
        </Button>
      )}

      <Button
        icon={<FolderOpenOutlined />}
        onClick={onNewSession}
        block
      >
        Load New Dataset
      </Button>
    </div>
  );
}

export default ProgressTracker;
