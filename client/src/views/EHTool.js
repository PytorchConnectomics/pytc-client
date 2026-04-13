import React, { useState, useEffect } from "react";
import { Layout } from "antd";
import DetectionWorkflow from "./ehtool/DetectionWorkflow";

const { Content } = Layout;

/**
 * EHTool Main Component
 * Mask proofreading workflow for reviewing slices in image stacks
 */
function EHTool({
  onStartProofreading,
  onSessionChange,
  refreshTrigger,
  savedSessionId,
  workflowId,
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
        <DetectionWorkflow
          sessionId={sessionId}
          setSessionId={setSessionId}
          workflowId={workflowId}
          onStartProofreading={onStartProofreading}
          refreshTrigger={refreshTrigger}
        />
      </Content>
    </Layout>
  );
}

export default EHTool;
