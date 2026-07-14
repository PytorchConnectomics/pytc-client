import React from "react";
import { Progress, Button, Divider, Space, Typography } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  ExclamationCircleOutlined,
  FolderOpenOutlined,
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
  compact = false,
  showLoadDataset = true,
}) {
  if (!stats) {
    return (
      <div style={{ padding: compact ? "0" : "16px" }}>
        <div
          style={{
            textAlign: "center",
            padding: compact ? "8px 4px" : "16px 8px",
          }}
        >
          <Text type="secondary">No session loaded yet.</Text>
        </div>
      </div>
    );
  }

  const progressPercent = stats.progress_percent || 0;

  return (
    <div style={{ padding: "0" }}>
      <Space
        direction="vertical"
        size={compact ? 4 : 6}
        style={{ width: "100%" }}
      >
        <Text strong style={{ fontSize: 13 }}>
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
            gap: compact ? 6 : 8,
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
            <QuestionCircleOutlined style={{ color: "#f59e0b" }} />{" "}
            {stats.unsure}
          </div>
          <div>
            <ExclamationCircleOutlined style={{ color: "#cbd5f5" }} />{" "}
            {stats.error}
          </div>
        </div>

        {showLoadDataset && (
          <>
            <Divider style={{ margin: compact ? "4px 0" : "8px 0" }} />

            <Space direction="vertical" style={{ width: "100%" }} size="small">
              <Button
                icon={<FolderOpenOutlined />}
                onClick={onNewSession}
                block
                size="small"
              >
                Load dataset
              </Button>
            </Space>
          </>
        )}
      </Space>
    </div>
  );
}

export default ProgressTracker;
