import React from "react";
import { Card, Button, Space, Divider, Tag } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  SelectOutlined,
  ClearOutlined,
} from "@ant-design/icons";
import InlineHelpChat from "../../components/InlineHelpChat";

/**
 * Classification Panel Component
 * Controls for classifying selected layers
 */
function ClassificationPanel({
  selectedCount,
  onClassify,
  onSelectAll,
  onClearSelection,
}) {
  const projectContext =
    "Mitochondria segmentation on an electron microscopy volume.";
  const taskContext =
    "Segmentation proofreading workflow (error handling tool).";

  return (
    <div style={{ padding: "16px" }}>
      <Card
        title={
          <Space align="center">
            <span>Classification</span>
            <InlineHelpChat
              taskKey="worm-error-handling"
              label="Classification"
              yamlKey="EHTOOL.CLASSIFICATION"
              value={selectedCount}
              projectContext={projectContext}
              taskContext={taskContext}
            />
          </Space>
        }
        size="small"
        style={{ marginBottom: "16px" }}
      >
        <div style={{ marginBottom: "16px" }}>
          <Tag color={selectedCount > 0 ? "blue" : "default"}>
            {selectedCount} layer{selectedCount !== 1 ? "s" : ""} selected
          </Tag>
        </div>

        <Space direction="vertical" style={{ width: "100%" }} size="small">
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => onClassify("correct")}
            disabled={selectedCount === 0}
            block
            style={{ background: "#52c41a", borderColor: "#52c41a" }}
          >
            Correct (C)
          </Button>

          <Button
            danger
            icon={<CloseCircleOutlined />}
            onClick={() => onClassify("incorrect")}
            disabled={selectedCount === 0}
            block
          >
            Incorrect (X)
          </Button>

          <Button
            icon={<QuestionCircleOutlined />}
            onClick={() => onClassify("unsure")}
            disabled={selectedCount === 0}
            block
            style={{
              background: "#faad14",
              borderColor: "#faad14",
              color: "#fff",
            }}
          >
            Unsure (U)
          </Button>
        </Space>
      </Card>

      <Card
        title={
          <Space align="center">
            <span>Selection</span>
            <InlineHelpChat
              taskKey="worm-error-handling"
              label="Selection"
              yamlKey="EHTOOL.SELECTION"
              value={selectedCount}
              projectContext={projectContext}
              taskContext={taskContext}
            />
          </Space>
        }
        size="small"
      >
        <Space direction="vertical" style={{ width: "100%" }} size="small">
          <Button icon={<SelectOutlined />} onClick={onSelectAll} block>
            Select All (Ctrl+A)
          </Button>

          <Button
            icon={<ClearOutlined />}
            onClick={onClearSelection}
            disabled={selectedCount === 0}
            block
          >
            Clear Selection
          </Button>
        </Space>
      </Card>

      <Divider />

      <div
        style={{
          padding: "12px",
          background: "#f5f5f5",
          borderRadius: "4px",
          fontSize: "12px",
        }}
      >
        <Space align="center" style={{ marginBottom: 4 }}>
          <h4 style={{ marginTop: 0, fontSize: "13px" }}>
            Keyboard Shortcuts:
          </h4>
          <InlineHelpChat
            taskKey="worm-error-handling"
            label="Keyboard shortcuts"
            yamlKey="EHTOOL.SHORTCUTS"
            value={null}
            projectContext={projectContext}
            taskContext={taskContext}
          />
        </Space>
        <ul style={{ marginBottom: 0, paddingLeft: "20px" }}>
          <li>
            <kbd>C</kbd> - Mark as Correct
          </li>
          <li>
            <kbd>X</kbd> - Mark as Incorrect
          </li>
          <li>
            <kbd>U</kbd> - Mark as Unsure
          </li>
          <li>
            <kbd>Ctrl+A</kbd> - Select All
          </li>
        </ul>
      </div>
    </div>
  );
}

export default ClassificationPanel;
