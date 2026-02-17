import React, { useState, useEffect } from "react";
import { Layout, Typography } from "antd";
import { BugOutlined } from "@ant-design/icons";
import DetectionWorkflow from "./ehtool/DetectionWorkflow";

const { Content } = Layout;
const { Title, Text } = Typography;

/**
 * EHTool Main Component
 * Mask proofreading workflow for reviewing slices in image stacks
 */
function EHTool({
  onStartProofreading,
  onSessionChange,
  refreshTrigger,
  savedSessionId,
}) {
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
    <Layout style={{ height: "100%", background: "#f6f8fb" }}>
      <Content style={{ padding: "20px 24px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 12,
          }}
        >
          <BugOutlined style={{ fontSize: 18, color: "#1677ff" }} />
          <div>
            <Title level={5} style={{ margin: 0 }}>
              Mask Proofreading
            </Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Review and correct instances in your volume.
            </Text>
          </div>
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
