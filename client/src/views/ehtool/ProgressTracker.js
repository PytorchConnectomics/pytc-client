import React from "react";
import { Card, Progress, Statistic, Row, Col, Button, Divider, Space } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  ExclamationCircleOutlined,
  FolderOpenOutlined,
  EditOutlined,
} from "@ant-design/icons";
import InlineHelpChat from "../../components/InlineHelpChat";

/**
 * Progress Tracker Component
 * Displays statistics and progress for the detection workflow
 */
function ProgressTracker({
  stats,
  projectName,
  totalLayers,
  onNewSession,
  onStartProofreading,
}) {
  const projectContext =
    "Mitochondria segmentation on an electron microscopy volume.";
  const taskContext =
    "Segmentation proofreading workflow (error handling tool).";

  if (!stats) {
    return (
      <div style={{ padding: "16px" }}>
        <Card>
          <div style={{ textAlign: "center", padding: "24px" }}>
            <p style={{ color: "#999" }}>No session loaded</p>
          </div>
        </Card>
      </div>
    );
  }

  const progressPercent = stats.progress_percent || 0;

  return (
    <div style={{ padding: "16px" }}>
      <Card
        title={
          <Space align="center">
            <span>Project Info</span>
            <InlineHelpChat
              taskKey="worm-error-handling"
              label="Project info"
              yamlKey="EHTOOL.PROJECT_INFO"
              value={projectName}
              projectContext={projectContext}
              taskContext={taskContext}
            />
          </Space>
        }
        size="small"
        style={{ marginBottom: "16px" }}
      >
        <div style={{ marginBottom: "8px" }}>
          <strong>{projectName}</strong>
        </div>
        <div style={{ fontSize: "12px", color: "#666" }}>
          {totalLayers} layers total
        </div>
      </Card>

      <Card
        title={
          <Space align="center">
            <span>Progress</span>
            <InlineHelpChat
              taskKey="worm-error-handling"
              label="Progress"
              yamlKey="EHTOOL.PROGRESS"
              value={stats.reviewed}
              projectContext={projectContext}
              taskContext={taskContext}
            />
          </Space>
        }
        size="small"
        style={{ marginBottom: "16px" }}
      >
        <Progress
          percent={progressPercent}
          status={progressPercent === 100 ? "success" : "active"}
          strokeColor={{
            "0%": "#108ee9",
            "100%": "#87d068",
          }}
        />
        <div
          style={{
            textAlign: "center",
            marginTop: "8px",
            fontSize: "12px",
            color: "#666",
          }}
        >
          {stats.reviewed} / {stats.total} layers reviewed
        </div>
      </Card>

      <Card
        title={
          <Space align="center">
            <span>Classification Summary</span>
            <InlineHelpChat
              taskKey="worm-error-handling"
              label="Classification Summary"
              yamlKey="EHTOOL.SUMMARY"
              value={stats}
              projectContext={projectContext}
              taskContext={taskContext}
            />
          </Space>
        }
        size="small"
        style={{ marginBottom: "16px" }}
      >
        <Row gutter={[8, 8]}>
          <Col span={12}>
            <Statistic
              title="Correct"
              value={stats.correct}
              prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
              valueStyle={{ fontSize: "20px" }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Incorrect"
              value={stats.incorrect}
              prefix={<CloseCircleOutlined style={{ color: "#ff4d4f" }} />}
              valueStyle={{ fontSize: "20px" }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Unsure"
              value={stats.unsure}
              prefix={<QuestionCircleOutlined style={{ color: "#faad14" }} />}
              valueStyle={{ fontSize: "20px" }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="Unreviewed"
              value={stats.error}
              prefix={
                <ExclamationCircleOutlined style={{ color: "#d9d9d9" }} />
              }
              valueStyle={{ fontSize: "20px" }}
            />
          </Col>
        </Row>
      </Card>

      <Divider />

      {stats && stats.incorrect > 0 && (
        <Space align="center" style={{ width: "100%", marginBottom: "12px" }}>
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={onStartProofreading}
            block
          >
            Proofread Incorrect Layers ({stats.incorrect})
          </Button>
          <InlineHelpChat
            taskKey="worm-error-handling"
            label="Proofread incorrect layers"
            yamlKey="EHTOOL.PROOFREAD"
            value={stats.incorrect}
            projectContext={projectContext}
            taskContext={taskContext}
          />
        </Space>
      )}

      <Space align="center" style={{ width: "100%" }}>
        <Button icon={<FolderOpenOutlined />} onClick={onNewSession} block>
          Load New Dataset
        </Button>
        <InlineHelpChat
          taskKey="worm-error-handling"
          label="Load new dataset"
          yamlKey="EHTOOL.NEW_DATASET"
          value={null}
          projectContext={projectContext}
          taskContext={taskContext}
        />
      </Space>
    </div>
  );
}

export default ProgressTracker;
