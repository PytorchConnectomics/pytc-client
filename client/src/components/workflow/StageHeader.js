import React from "react";
import { Button, Space, Tooltip, Typography } from "antd";

import { getStageMeta } from "../../design/workflowDesignSystem";

const { Text } = Typography;

function StageHeader({
  stage,
  title = "Segmentation Workflow",
  subtitle,
  actionLabel,
  onAction,
}) {
  const meta = getStageMeta(stage);
  return (
    <div className={`workflow-stage-header workflow-tone-${meta.tone}`}>
      <div className="workflow-stage-copy">
        <Space size="small" wrap>
          <Tooltip title={subtitle || meta.description}>
            <Text strong className="workflow-stage-title">
              {title}
            </Text>
          </Tooltip>
        </Space>
      </div>
      {actionLabel && (
        <Button size="small" type="text" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export default StageHeader;
