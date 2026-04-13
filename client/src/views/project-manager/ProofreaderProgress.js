import React, { useMemo } from "react";
import {
  Card,
  Table,
  Avatar,
  Progress,
  Typography,
  Row,
  Col,
  Tag,
  Space,
  Badge,
  Tooltip,
  Divider,
  Button,
  Popconfirm,
  Spin,
} from "antd";
import {
  UserOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  RiseOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useProjectManager } from "../../contexts/ProjectManagerContext";

const { Title, Text } = Typography;

// ─── Read-only display pill (for metrics that must not look editable) ─────────
const ReadOnlyPill = ({ children, color = "#595959", bg = "#fafafa" }) => (
  <span
    style={{
      display: "inline-block",
      background: bg,
      border: "1px solid #f0f0f0",
      borderRadius: 12,
      padding: "1px 10px",
      fontSize: 12,
      color,
      cursor: "default",
      userSelect: "none",
    }}
  >
    {children}
  </span>
);

// ─── Sub-components ──────────────────────────────────────────────────────────

function WeeklyThroughputChart({ throughput }) {
  const W = 800;
  const H = 150;
  const PAD = 40;
  const chartW = W - PAD * 2;
  const chartH = H - PAD;

  if (!throughput || throughput.length === 0) return null;
  const maxVal = Math.max(...throughput.map((d) => d.count)) * 1.1;
  const barWidth = (chartW / throughput.length) * 0.6;
  const gap = (chartW / throughput.length) * 0.4;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H }}>
      {[0, 0.5, 1].map((f) => (
        <line
          key={f}
          x1={PAD}
          y1={PAD / 2 + chartH * (1 - f)}
          x2={PAD + chartW}
          y2={PAD / 2 + chartH * (1 - f)}
          stroke="#f0f0f0"
          strokeWidth={1}
        />
      ))}
      {throughput.map((d, i) => {
        const x = PAD + i * (barWidth + gap) + gap / 2;
        const barH = (d.count / maxVal) * chartH;
        const y = PAD / 2 + chartH - barH;
        return (
          <g key={d.day}>
            <Tooltip title={`${d.day}: ${d.count} items`}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barH}
                fill="#1890ff"
                rx={4}
                opacity={0.8}
              />
            </Tooltip>
            <text
              x={x + barWidth / 2}
              y={PAD / 2 + chartH + 16}
              textAnchor="middle"
              fontSize={10}
              fill="#8c8c8c"
            >
              {d.day}
            </text>
            <text
              x={x + barWidth / 2}
              y={y - 6}
              textAnchor="middle"
              fontSize={9}
              fill="#595959"
              fontWeight="600"
            >
              {d.count.toLocaleString()}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

function ProofreaderProgress() {
  const {
    quotaData,
    proofreaderData,
    throughputData,
    saving,
    resetData,
    isWorker,
  } = useProjectManager();

  // Helper to get calculated stats for a proofreader from quotaData
  const getStats = (key) => {
    const quota = quotaData.find((q) => q.key === key);
    if (!quota) return { target: 1500, actual: 0 };
    const target =
      quota.mon +
      quota.tue +
      quota.wed +
      quota.thu +
      quota.fri +
      quota.sat +
      quota.sun;
    const actual =
      (quota.actualMon || 0) +
      (quota.actualTue || 0) +
      (quota.actualWed || 0) +
      (quota.actualThu || 0) +
      (quota.actualFri || 0) +
      (quota.actualSat || 0) +
      (quota.actualSun || 0);
    return { target, actual };
  };

  const topPerformers = useMemo(() => {
    const withPoints = proofreaderData.map((p) => ({
      ...p,
      weeklyPoints: getStats(p.key).actual,
    }));
    return [...withPoints]
      .sort((a, b) => b.weeklyPoints - a.weeklyPoints)
      .slice(0, 3);
  }, [proofreaderData, quotaData]);

  const teamAccuracy =
    proofreaderData.length > 0
      ? (
          proofreaderData.reduce((sum, p) => sum + p.accuracy, 0) /
          proofreaderData.length
        ).toFixed(1)
      : 0;

  const COLUMNS = [
    {
      title: "Proofreader",
      dataIndex: "name",
      key: "name",
      render: (name, record) => (
        <Space>
          <Avatar
            style={{ backgroundColor: record.avatarColor }}
            icon={<UserOutlined />}
            size="small"
          />
          <div>
            <Text strong style={{ display: "block", lineHeight: "1.2" }}>
              {name}
            </Text>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {record.role}
            </Text>
          </div>
        </Space>
      ),
    },
    {
      title: "Total Points",
      dataIndex: "totalPoints",
      key: "totalPoints",
      align: "right",
      render: (pts) => <Text strong>{pts.toLocaleString()}</Text>,
    },
    {
      title: "This Week",
      key: "weeklyProgress",
      align: "right",
      render: (_, record) => {
        const { target, actual } = getStats(record.key);
        const pct = target > 0 ? Math.round((actual / target) * 100) : 0;
        return (
          <Space
            direction="vertical"
            size={0}
            align="end"
            style={{ width: "100%" }}
          >
            <Text>
              {actual.toLocaleString()}{" "}
              <Text type="secondary" style={{ fontSize: 11 }}>
                / {target.toLocaleString()}
              </Text>
            </Text>
            <Progress
              percent={pct}
              size={[60, 4]}
              showInfo={false}
              strokeColor={actual >= target ? "#52c41a" : "#1890ff"}
            />
          </Space>
        );
      },
    },
    {
      title: "Accuracy",
      dataIndex: "accuracy",
      key: "accuracy",
      align: "center",
      render: (pct) => (
        <ReadOnlyPill
          color={pct >= 95 ? "#52c41a" : pct >= 90 ? "#faad14" : "#f5222d"}
          bg={pct >= 95 ? "#f6ffed" : pct >= 90 ? "#fffbe6" : "#fff2f0"}
        >
          {pct}%
        </ReadOnlyPill>
      ),
    },
    {
      title: "Last Active",
      dataIndex: "lastActive",
      key: "lastActive",
      render: (time, record) => (
        <Space>
          <Badge
            status={
              record.status === "online"
                ? "success"
                : record.status === "away"
                  ? "warning"
                  : "default"
            }
          />
          <ReadOnlyPill>{time}</ReadOnlyPill>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: "0 4px" }}>
      {/* ── Header ── */}
      <div
        style={{
          marginBottom: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0 }}>
            {isWorker ? "My Performance" : "Proofreader Performance"}
          </Title>
          <Text type="secondary">
            {isWorker
              ? "Your personal throughput and accuracy · auto-saved to server"
              : "Real-time throughput and accuracy tracking · auto-saved to server"}
            {saving && (
              <>
                {" "}
                · <Spin size="small" style={{ marginLeft: 6 }} /> saving…
              </>
            )}
          </Text>
        </div>
        <Popconfirm
          title="Reset all progress data to defaults?"
          description="This will overwrite server data with original seed values."
          onConfirm={resetData}
          okText="Reset"
          cancelText="Cancel"
          okButtonProps={{ danger: true }}
        >
          <Button icon={<ReloadOutlined />} danger>
            Reset to Defaults
          </Button>
        </Popconfirm>
      </div>

      {/* ── Top Row: Individual Cards ── */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        {proofreaderData.map((pr) => {
          const { target, actual } = getStats(pr.key);
          const pct = target > 0 ? Math.round((actual / target) * 100) : 0;
          return (
            <Col span={4.8} key={pr.key} style={{ width: "20%" }}>
              <Card size="small" hoverable style={{ borderRadius: 8 }}>
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                    }}
                  >
                    <Avatar
                      size={40}
                      style={{ backgroundColor: pr.avatarColor }}
                      icon={<UserOutlined />}
                    />
                    <Badge
                      status={pr.status === "online" ? "success" : "default"}
                    />
                  </div>
                  <div>
                    <Text strong style={{ fontSize: 13, display: "block" }}>
                      {pr.name}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {pr.role}
                    </Text>
                  </div>
                  <div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 4,
                      }}
                    >
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        Weekly Goal
                      </Text>
                      <Text strong style={{ fontSize: 11 }}>
                        {pct}%
                      </Text>
                    </div>
                    <Progress
                      percent={pct}
                      size="small"
                      showInfo={false}
                      strokeColor={actual >= target ? "#52c41a" : "#1890ff"}
                    />
                    <Text type="secondary" style={{ fontSize: 10 }}>
                      {actual.toLocaleString()} / {target.toLocaleString()} pts
                    </Text>
                  </div>
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* ── Main Section: Table + Insights ── */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={18}>
          <Card
            size="small"
            title={
              <Text strong>
                <ThunderboltOutlined /> Active Session Metrics
              </Text>
            }
          >
            <Table
              dataSource={proofreaderData}
              columns={COLUMNS}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        <Col span={6}>
          <Card
            size="small"
            title={
              <Text strong>
                <RiseOutlined /> Top Performers
              </Text>
            }
            style={{ height: "100%" }}
          >
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              {topPerformers.map((pr, idx) => (
                <div
                  key={pr.key}
                  style={{ display: "flex", gap: 12, alignItems: "center" }}
                >
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      background:
                        idx === 0
                          ? "#ffd700"
                          : idx === 1
                            ? "#c0c0c0"
                            : "#cd7f32",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: "bold",
                      color: "#fff",
                      fontSize: 12,
                    }}
                  >
                    {idx + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <Text strong style={{ fontSize: 12 }}>
                      {pr.name}
                    </Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {pr.weeklyPoints.toLocaleString()} pts this week
                    </Text>
                  </div>
                  <Tag color="blue" bordered={false} style={{ margin: 0 }}>
                    +{Math.round(pr.accuracy)}% acc
                  </Tag>
                </div>
              ))}

              <Divider style={{ margin: "8px 0" }} />

              <div>
                <Text strong style={{ fontSize: 12 }}>
                  <CheckCircleOutlined style={{ color: "#52c41a" }} /> Team
                  Accuracy
                </Text>
                <div style={{ marginTop: 8 }}>
                  <Progress
                    percent={parseFloat(teamAccuracy)}
                    status="active"
                    strokeColor="#52c41a"
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    Target: 95.0%
                  </Text>
                </div>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* ── Bottom Section: Team Throughput ── */}
      <Card
        size="small"
        title={
          <Text strong>
            <ClockCircleOutlined /> Team Throughput (Last 7 Days)
          </Text>
        }
      >
        <WeeklyThroughputChart throughput={throughputData} />
      </Card>
    </div>
  );
}

export default ProofreaderProgress;
