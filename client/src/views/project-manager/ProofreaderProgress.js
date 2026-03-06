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
} from "antd";
import {
    UserOutlined,
    CheckCircleOutlined,
    ClockCircleOutlined,
    ThunderboltOutlined,
    RiseOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";

const { Title, Text } = Typography;

// ─── Seed Data ───────────────────────────────────────────────────────────────

const PROOFREADERS = [
    {
        key: "1",
        name: "Alex Rivera",
        avatarColor: "#1890ff",
        role: "Senior Annotator",
        totalPoints: 12450,
        weeklyPoints: 1420,
        weeklyQuota: 1750,
        accuracy: 98.5,
        lastActive: "2 mins ago",
        status: "online",
    },
    {
        key: "2",
        name: "Jordan Smith",
        avatarColor: "#52c41a",
        role: "Proofreader",
        totalPoints: 8900,
        weeklyPoints: 1100,
        weeklyQuota: 1500,
        accuracy: 94.2,
        lastActive: "15 mins ago",
        status: "online",
    },
    {
        key: "3",
        name: "Sam Taylor",
        avatarColor: "#fadb14",
        role: "Proofreader",
        totalPoints: 5600,
        weeklyPoints: 850,
        weeklyQuota: 1500,
        accuracy: 92.1,
        lastActive: "1 hour ago",
        status: "away",
    },
    {
        key: "4",
        name: "Casey Chen",
        avatarColor: "#eb2f96",
        role: "Junior Annotator",
        totalPoints: 3200,
        weeklyPoints: 1250,
        weeklyQuota: 1200,
        accuracy: 96.8,
        lastActive: "3 hours ago",
        status: "offline",
    },
    {
        key: "5",
        name: "Robin Banks",
        avatarColor: "#722ed1",
        role: "Proofreader",
        totalPoints: 7100,
        weeklyPoints: 300,
        weeklyQuota: 1500,
        accuracy: 89.5,
        lastActive: "Yesterday",
        status: "offline",
    },
];

// Team daily throughput (last 7 days)
const DAILY_THROUGHPUT = [
    { day: "Mon", count: 4200 },
    { day: "Tue", count: 3800 },
    { day: "Wed", count: 5100 },
    { day: "Thu", count: 4700 },
    { day: "Fri", count: 5300 },
    { day: "Sat", count: 1200 },
    { day: "Sun", count: 900 },
];

// ─── Sub-components ──────────────────────────────────────────────────────────

function WeeklyThroughputChart() {
    const W = 800;
    const H = 150;
    const PAD = 40;
    const chartW = W - PAD * 2;
    const chartH = H - PAD;

    const maxVal = Math.max(...DAILY_THROUGHPUT.map(d => d.count)) * 1.1;
    const barWidth = (chartW / DAILY_THROUGHPUT.length) * 0.6;
    const gap = (chartW / DAILY_THROUGHPUT.length) * 0.4;

    return (
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H }}>
            {/* Grid lines */}
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

            {DAILY_THROUGHPUT.map((d, i) => {
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

// ─── Column definitions ───────────────────────────────────────────────────────

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
                    <Text strong style={{ display: "block", lineHeight: "1.2" }}>{name}</Text>
                    <Text type="secondary" style={{ fontSize: 11 }}>{record.role}</Text>
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
        dataIndex: "weeklyPoints",
        key: "weeklyPoints",
        align: "right",
        render: (pts, record) => (
            <Space direction="vertical" size={0} align="end" style={{ width: "100%" }}>
                <Text>{pts.toLocaleString()}</Text>
                <Progress
                    percent={Math.round((pts / record.weeklyQuota) * 100)}
                    size={[60, 4]}
                    showInfo={false}
                    strokeColor={pts >= record.weeklyQuota ? "#52c41a" : "#1890ff"}
                />
            </Space>
        ),
    },
    {
        title: "Accuracy",
        dataIndex: "accuracy",
        key: "accuracy",
        align: "center",
        render: (pct) => (
            <Tag color={pct >= 95 ? "success" : pct >= 90 ? "warning" : "error"} style={{ borderRadius: 12 }}>
                {pct}%
            </Tag>
        ),
    },
    {
        title: "Last Active",
        dataIndex: "lastActive",
        key: "lastActive",
        render: (time, record) => (
            <Space>
                <Badge status={record.status === "online" ? "success" : record.status === "away" ? "warning" : "default"} />
                <Text type="secondary">{time}</Text>
            </Space>
        ),
    },
];

// ─── Main Component ───────────────────────────────────────────────────────────

function ProofreaderProgress() {
    const topPerformers = useMemo(() =>
        [...PROOFREADERS].sort((a, b) => b.weeklyPoints - a.weeklyPoints).slice(0, 3)
        , []);

    return (
        <div style={{ padding: "0 4px" }}>
            {/* ── Header ── */}
            <div style={{ marginBottom: 20 }}>
                <Title level={4} style={{ margin: 0 }}>Proofreader Performance</Title>
                <Text type="secondary">Real-time throughput and accuracy tracking</Text>
            </div>

            {/* ── Top Row: Individual Cards ── */}
            <Row gutter={16} style={{ marginBottom: 20 }}>
                {PROOFREADERS.map((pr) => (
                    <Col span={4.8} key={pr.key} style={{ width: "20%" }}>
                        <Card size="small" hoverable style={{ borderRadius: 8 }}>
                            <Space direction="vertical" size={12} style={{ width: "100%" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                    <Avatar
                                        size={40}
                                        style={{ backgroundColor: pr.avatarColor }}
                                        icon={<UserOutlined />}
                                    />
                                    <Badge status={pr.status === "online" ? "success" : "default"} />
                                </div>
                                <div>
                                    <Text strong style={{ fontSize: 13, display: "block" }}>{pr.name}</Text>
                                    <Text type="secondary" style={{ fontSize: 11 }}>{pr.role}</Text>
                                </div>
                                <div>
                                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                                        <Text type="secondary" style={{ fontSize: 11 }}>Weekly Quota</Text>
                                        <Text strong style={{ fontSize: 11 }}>
                                            {Math.round((pr.weeklyPoints / pr.weeklyQuota) * 100)}%
                                        </Text>
                                    </div>
                                    <Progress
                                        percent={Math.round((pr.weeklyPoints / pr.weeklyQuota) * 100)}
                                        size="small"
                                        showInfo={false}
                                        strokeColor={pr.weeklyPoints >= pr.weeklyQuota ? "#52c41a" : "#1890ff"}
                                    />
                                    <Text type="secondary" style={{ fontSize: 10 }}>
                                        {pr.weeklyPoints} / {pr.weeklyQuota} pts
                                    </Text>
                                </div>
                            </Space>
                        </Card>
                    </Col>
                ))}
            </Row>

            {/* ── Main Section: Table ── */}
            <Row gutter={16} style={{ marginBottom: 20 }}>
                <Col span={18}>
                    <Card
                        size="small"
                        title={<Text strong><ThunderboltOutlined /> Active Session Metrics</Text>}
                    >
                        <Table
                            dataSource={PROOFREADERS}
                            columns={COLUMNS}
                            pagination={false}
                            size="small"
                        />
                    </Card>
                </Col>

                {/* Right Panel: Insights */}
                <Col span={6}>
                    <Card
                        size="small"
                        title={<Text strong><RiseOutlined /> Top Performers</Text>}
                        style={{ height: "100%" }}
                    >
                        <Space direction="vertical" size={16} style={{ width: "100%" }}>
                            {topPerformers.map((pr, idx) => (
                                <div key={pr.key} style={{ display: "flex", gap: 12, alignItems: "center" }}>
                                    <div style={{
                                        width: 24, height: 24, borderRadius: "50%",
                                        background: idx === 0 ? "#ffd700" : idx === 1 ? "#c0c0c0" : "#cd7f32",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        fontWeight: "bold", color: "#fff", fontSize: 12
                                    }}>
                                        {idx + 1}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <Text strong style={{ fontSize: 12 }}>{pr.name}</Text>
                                        <br />
                                        <Text type="secondary" style={{ fontSize: 11 }}>{pr.weeklyPoints.toLocaleString()} pts this week</Text>
                                    </div>
                                    <Tag color="blue" bordered={false} style={{ margin: 0 }}>+{Math.round(pr.accuracy)}% acc</Tag>
                                </div>
                            ))}

                            <Divider style={{ margin: "8px 0" }} />

                            <div>
                                <Text strong style={{ fontSize: 12 }}><CheckCircleOutlined style={{ color: "#52c41a" }} /> Team Accuracy</Text>
                                <div style={{ marginTop: 8 }}>
                                    <Progress percent={95.4} status="active" strokeColor="#52c41a" title="Group average" />
                                    <Text type="secondary" style={{ fontSize: 11 }}>Target: 95.0%</Text>
                                </div>
                            </div>
                        </Space>
                    </Card>
                </Col>
            </Row>

            {/* ── Bottom Section: Team Throughput ── */}
            <Card
                size="small"
                title={<Text strong><ClockCircleOutlined /> Team Throughput (Last 7 Days)</Text>}
            >
                <WeeklyThroughputChart />
            </Card>
        </div>
    );
}

export default ProofreaderProgress;
