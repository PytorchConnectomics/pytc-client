import React from "react";
import { Card, Button, Space, Divider, Tag, Typography } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  SelectOutlined,
  ClearOutlined,
} from "@ant-design/icons";

/**
 * Classification Panel Component
 * Controls for classifying selected slices
 */
function ClassificationPanel({
  selectedCount,
  onClassify,
  onSelectAll,
  onClearSelection,
}) {
  const { Text } = Typography;

  return (
    <div style={{ padding: "16px" }}>
      <Card
        title="Classification"
        size="small"
        style={{
          marginBottom: "12px",
          background: "#fff",
          boxShadow: "0 6px 20px rgba(15, 23, 42, 0.06)",
        }}
      >
        <div style={{ marginBottom: "16px" }}>
          <Tag color={selectedCount > 0 ? "blue" : "default"}>
            {selectedCount} slice{selectedCount !== 1 ? "s" : ""} selected
          </Tag>
        </div>

        <Space direction="vertical" style={{ width: "100%" }} size="small">
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => onClassify("correct")}
            disabled={selectedCount === 0}
            block
            style={{ background: "#22c55e", borderColor: "#22c55e" }}
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
              background: "#f59e0b",
              borderColor: "#f59e0b",
              color: "#1f2937",
            }}
          >
            Unsure (U)
          </Button>
        </Space>
      </Card>

      <Card
        title="Selection"
        size="small"
        style={{
          background: "#fff",
          boxShadow: "0 6px 20px rgba(15, 23, 42, 0.06)",
        }}
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
          background: "#f8fafc",
          borderRadius: "4px",
          fontSize: "12px",
        }}
      >
        <Text strong style={{ fontSize: 12 }}>
          Keyboard shortcuts
        </Text>
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
