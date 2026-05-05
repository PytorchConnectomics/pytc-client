import React, { useState } from "react";
import { Button, Typography } from "antd";
import { DownOutlined, RightOutlined } from "@ant-design/icons";

const { Text } = Typography;

function AssistantTrace({ trace = [] }) {
  const [open, setOpen] = useState(false);
  const items = Array.isArray(trace) ? trace.filter(Boolean) : [];
  if (!items.length) return null;

  return (
    <div style={{ marginTop: 2 }}>
      <Button
        type="text"
        size="small"
        icon={open ? <DownOutlined /> : <RightOutlined />}
        onClick={() => setOpen((value) => !value)}
        style={{
          height: 24,
          paddingInline: 0,
          color: "#6b7280",
          fontSize: 12,
          fontWeight: 500,
        }}
      >
        What I checked
      </Button>
      {open && (
        <div
          style={{
            borderLeft: "2px solid #e5e7eb",
            display: "grid",
            gap: 6,
            marginTop: 2,
            paddingLeft: 10,
          }}
        >
          {items.map((item, index) => (
            <div key={`${item.label || "trace"}-${index}`}>
              <Text style={{ color: "#374151", display: "block", fontSize: 12 }}>
                {item.label || "Checked context"}
              </Text>
              {item.detail && (
                <Text type="secondary" style={{ display: "block", fontSize: 12 }}>
                  {item.detail}
                </Text>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AssistantTrace;
