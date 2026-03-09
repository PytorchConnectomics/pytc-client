import React, { useMemo, useRef, useState, useEffect } from "react";
import { Input, Tag, Space, Typography, Button } from "antd";
import { LeftOutlined, RightOutlined } from "@ant-design/icons";

const { Text } = Typography;

const statusColor = {
  correct: "green",
  incorrect: "red",
  unsure: "gold",
  error: "default",
};

const statusLabel = {
  correct: "reviewed",
  incorrect: "needs fix",
  unsure: "unsure",
  error: "unreviewed",
};

function InstanceNavigator({
  instances,
  activeInstanceId,
  onSelect,
  onPrev,
  onNext,
  filterText,
  onFilterText,
  instanceMode,
  showSummary = true,
}) {
  const listRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(360);
  const rowHeight = 76;
  const overscan = 6;

  useEffect(() => {
    if (!listRef.current) return;
    const handleResize = () => {
      setContainerHeight(listRef.current.clientHeight);
    };
    handleResize();
    const ro = new ResizeObserver(handleResize);
    ro.observe(listRef.current);
    return () => ro.disconnect();
  }, []);

  const filtered = useMemo(() => {
    if (!filterText) return instances;
    const lower = filterText.toLowerCase();
    return instances.filter((inst) =>
      `${inst.id}`.toLowerCase().includes(lower),
    );
  }, [instances, filterText]);

  const activeInstance = useMemo(
    () => instances.find((inst) => inst.id === activeInstanceId) || null,
    [instances, activeInstanceId],
  );

  const total = filtered.length;
  const startIndex = Math.max(
    0,
    Math.floor(scrollTop / rowHeight) - overscan,
  );
  const endIndex = Math.min(
    total,
    Math.ceil((scrollTop + containerHeight) / rowHeight) + overscan,
  );
  const visibleItems = filtered.slice(startIndex, endIndex);
  const paddingTop = startIndex * rowHeight;
  const paddingBottom = (total - endIndex) * rowHeight;

  return (
    <div style={{ padding: "0" }}>
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Text style={{ fontSize: 12 }} strong>
          Instances
        </Text>
        {instanceMode && instanceMode !== "none" && (
          <Tag color="blue" style={{ fontSize: 11 }}>
            {instanceMode === "semantic" ? "semantic (derived)" : "instance"}
          </Tag>
        )}
      </Space>

      <Space style={{ marginTop: 8 }}>
        <Button size="small" icon={<LeftOutlined />} onClick={onPrev} />
        <Button size="small" icon={<RightOutlined />} onClick={onNext} />
      </Space>

      <Input
        placeholder="Filter"
        value={filterText}
        onChange={(e) => onFilterText(e.target.value)}
        style={{ marginTop: 8 }}
        size="small"
      />

      {showSummary && (
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {activeInstance
              ? `Selected #${activeInstance.id} • ${total} total`
              : `${total} total`}
          </Text>
        </div>
      )}

      <div
        ref={listRef}
        style={{
          marginTop: 12,
          maxHeight: "60vh",
          overflow: "auto",
        }}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        <div style={{ paddingTop, paddingBottom }}>
          {visibleItems.map((item) => (
            <div
              key={item.id}
              onClick={() => onSelect(item)}
              style={{
                cursor: "pointer",
                borderRadius: 8,
                padding: "10px 12px",
                marginBottom: 6,
                height: rowHeight - 6,
                boxSizing: "border-box",
                background:
                  item.id === activeInstanceId ? "#e0f2fe" : "transparent",
                border: "1px solid #f1f5f9",
              }}
            >
              <div style={{ width: "100%" }}>
                <Space style={{ width: "100%", justifyContent: "space-between" }}>
                  <Text style={{ fontSize: 12 }} strong>
                    #{item.id}
                  </Text>
                  <Tag color={statusColor[item.classification]} style={{ fontSize: 10 }}>
                    {statusLabel[item.classification]}
                  </Tag>
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  COM: {item.com_z}, {item.com_y}, {item.com_x}
                </Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  voxels: {item.voxel_count}
                </Text>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default InstanceNavigator;
