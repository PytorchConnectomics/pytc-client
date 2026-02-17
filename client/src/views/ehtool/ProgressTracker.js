import React from "react";
import {
  Card,
  Progress,
  Statistic,
  Row,
  Col,
  Button,
  Divider,
  Space,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  ExclamationCircleOutlined,
  FolderOpenOutlined,
  EditOutlined,
} from "@ant-design/icons";
const { Text } = Typography;

/**
 * Progress Tracker Component
 * Displays statistics and progress for the detection workflow
 */
function ProgressTracker({
  stats,
  projectName,
  totalLayers,
  unitLabel = "slices",
  onNewSession,
  onStartProofreading,
  onJumpToNext,
}) {
  if (!stats) {
    return (
      <div style={{ padding: "16px" }}>
        <Card bordered={false} style={{ background: "#f8fafc" }}>
          <div style={{ textAlign: "center", padding: "16px 8px" }}>
            <Text type="secondary">No session loaded yet.</Text>
          </div>
        </Card>
      </div>
    );
  }

  const progressPercent = stats.progress_percent || 0;

  return (
    <div style={{ padding: "0" }}>
      <Space direction="vertical" size={6} style={{ width: "100%" }}>
        <Text strong style={{ fontSize: 13 }}>
          {projectName}
        </Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {totalLayers} {unitLabel}
        </Text>
        <Progress
          percent={progressPercent}
          status={progressPercent === 100 ? "success" : "active"}
          size="small"
          strokeColor="#3b82f6"
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          {stats.reviewed} / {stats.total} reviewed
        </Text>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
            fontSize: 12,
          }}
        >
          <div>
            <CheckCircleOutlined style={{ color: "#22c55e" }} /> {stats.correct}
          </div>
          <div>
            <CloseCircleOutlined style={{ color: "#ef4444" }} />{" "}
            {stats.incorrect}
          </div>
          <div>
            <QuestionCircleOutlined style={{ color: "#f59e0b" }} /> {stats.unsure}
          </div>
          <div>
            <ExclamationCircleOutlined style={{ color: "#cbd5f5" }} />{" "}
            {stats.error}
          </div>
        </div>

        <Divider style={{ margin: "8px 0" }} />

        <Space direction="vertical" style={{ width: "100%" }} size="small">
          {onJumpToNext && (
            <Button type="primary" onClick={onJumpToNext} block size="small">
              Next unreviewed
            </Button>
          )}
          <Button icon={<FolderOpenOutlined />} onClick={onNewSession} block size="small">
            Load dataset
          </Button>
        </Space>
      </Space>
    </div>
  );
}

export default ProgressTracker;
