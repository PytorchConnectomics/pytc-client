import React, { useState, useMemo } from "react";
import {
    Card,
    Statistic,
    Table,
    Tag,
    Progress,
    Button,
    Space,
    Typography,
    Tooltip,
    Row,
    Col,
    Divider,
    Badge,
} from "antd";
import {
    CheckCircleOutlined,
    ClockCircleOutlined,
    StopOutlined,
    MinusCircleOutlined,
    WarningOutlined,
    RiseOutlined,
    TeamOutlined,
    FileTextOutlined,
    ThunderboltOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";

const { Title, Text } = Typography;

// ─── Seed Data ───────────────────────────────────────────────────────────────

const PROJECT_START = dayjs("2025-10-01");
const PROJECT_END = dayjs("2026-03-31");

const MILESTONES = [
    { label: "Model v1", date: dayjs("2025-11-15"), color: "#1890ff" },
    { label: "Mid-Review", date: dayjs("2025-12-20"), color: "#722ed1" },
    { label: "Model v2", date: dayjs("2026-01-28"), color: "#1890ff" },
    { label: "Data Freeze", date: dayjs("2026-02-15"), color: "#fa8c16" },
    { label: "Model v3", date: dayjs("2026-03-20"), color: "#1890ff" },
];

const DATASETS = [
    {
        key: "1",
        name: "Hippocampus_CA3",
        experiment: "Synapse detection",
        total: 12450,
        proofread: 38,
        status: "in_progress",
        eta: "Jan 18",
        priority: "high",
    },
    {
        key: "2",
        name: "Motor_Cortex_M1",
        experiment: "Axon tracing",
        total: 9800,
        proofread: 72,
        status: "in_progress",
        eta: "Jan 22",
        priority: "high",
    },
    {
        key: "3",
        name: "Cerebellum_PC",
        experiment: "Dendrite segmentation",
        total: 6200,
        proofread: 91,
        status: "done",
        eta: "Complete",
        priority: "normal",
    },
    {
        key: "4",
        name: "Retina_GCL",
        experiment: "Cell classification",
        total: 3300,
        proofread: 5,
        status: "blocked",
        eta: "TBD",
        priority: "high",
    },
    {
        key: "5",
        name: "Olfactory_Bulb",
        experiment: "Glomeruli mapping",
        total: 7650,
        proofread: 0,
        status: "not_started",
        eta: "Feb 28",
        priority: "normal",
    },
    {
        key: "6",
        name: "Visual_Cortex_V1",
        experiment: "Spine detection",
        total: 15000,
        proofread: 55,
        status: "in_progress",
        eta: "Feb 10",
        priority: "normal",
    },
];

// Weekly cumulative progress (weeks 1–26)
const CUMULATIVE_DATA = [
    0, 480, 1100, 1950, 2800, 3900, 5100, 6200, 7450, 8600, 9900, 11200, 12600,
    13900, 15400, 17000, 18500, 20100, 21800, 23400, 25000, 26700, 28500, 30200,
    32000, 33800,
];
const CUMULATIVE_TARGET = [
    0, 600, 1200, 1800, 2400, 3000, 3600, 4800, 6000, 7200, 8400, 9600, 10800,
    12000, 13200, 14400, 15600, 16800, 18000, 19200, 20400, 21600, 22800, 24000,
    25200, 26400,
];

const AT_RISK = [
    { label: "Hippocampus_CA3", reason: "Low progress (38%)", icon: "progress" },
    { label: "Motor_Cortex_M1", reason: "Deadline approaching", icon: "clock" },
    { label: "Retina_GCL", reason: "Blocked — awaiting data", icon: "blocked" },
];

const UPCOMING_MILESTONES = [
    { label: "Model v2 data freeze", date: "JAN 28" },
    { label: "Mid-project review", date: "FEB 5" },
    { label: "Final data freeze", date: "FEB 15" },
    { label: "Model v3 launch", date: "MAR 20" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_META = {
    in_progress: { label: "In Progress", color: "processing" },
    done: { label: "Done", color: "success" },
    blocked: { label: "Blocked", color: "error" },
    not_started: { label: "Not Started", color: "default" },
};

function statusTag(status) {
    const { label, color } = STATUS_META[status] || {};
    return <Badge status={color} text={label} />;
}

// Convert a date to a 0-1 fraction along the 6-month timeline
function dateToFrac(d) {
    const total = PROJECT_END.diff(PROJECT_START, "day");
    const elapsed = dayjs(d).diff(PROJECT_START, "day");
    return Math.min(1, Math.max(0, elapsed / total));
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Custom SVG 6-month horizontal timeline */
function SixMonthTimeline() {
    const W = 900; // viewBox width
    const H = 80;
    const PAD = 40;
    const trackY = 48;
    const trackW = W - PAD * 2;

    // Month tick marks
    const months = [];
    let cur = PROJECT_START.startOf("month");
    while (cur.isBefore(PROJECT_END) || cur.isSame(PROJECT_END, "month")) {
        months.push(cur);
        cur = cur.add(1, "month");
    }

    // Today marker
    const todayFrac = dateToFrac(dayjs("2026-03-02"));

    return (
        <svg
            viewBox={`0 0 ${W} ${H}`}
            style={{ width: "100%", height: H }}
            aria-label="6-month annotation project timeline"
        >
            {/* Track background */}
            <rect
                x={PAD}
                y={trackY - 4}
                width={trackW}
                height={8}
                rx={4}
                fill="#e8e8e8"
            />
            {/* Progress fill */}
            <rect
                x={PAD}
                y={trackY - 4}
                width={trackW * todayFrac}
                height={8}
                rx={4}
                fill="#1890ff"
                opacity={0.3}
            />

            {/* Month ticks */}
            {months.map((m) => {
                const x = PAD + dateToFrac(m) * trackW;
                return (
                    <g key={m.format("YYYY-MM")}>
                        <line x1={x} y1={trackY + 4} x2={x} y2={trackY + 12} stroke="#bfbfbf" strokeWidth={1} />
                        <text x={x} y={trackY + 24} textAnchor="middle" fontSize={10} fill="#8c8c8c">
                            {m.format("MMM")}
                        </text>
                    </g>
                );
            })}

            {/* Milestones */}
            {MILESTONES.map((ms) => {
                const x = PAD + dateToFrac(ms.date) * trackW;
                return (
                    <Tooltip key={ms.label} title={`${ms.label} — ${ms.date.format("MMM D, YYYY")}`}>
                        <g style={{ cursor: "pointer" }}>
                            {/* Diamond shape */}
                            <polygon
                                points={`${x},${trackY - 10} ${x + 7},${trackY} ${x},${trackY + 10} ${x - 7},${trackY}`}
                                fill={ms.color}
                            />
                            <text x={x} y={trackY - 14} textAnchor="middle" fontSize={9} fontWeight="600" fill={ms.color}>
                                {ms.label}
                            </text>
                        </g>
                    </Tooltip>
                );
            })}

            {/* Today marker */}
            <line
                x1={PAD + todayFrac * trackW}
                y1={trackY - 18}
                x2={PAD + todayFrac * trackW}
                y2={trackY + 14}
                stroke="#f5222d"
                strokeWidth={1.5}
                strokeDasharray="3 2"
            />
            <text
                x={PAD + todayFrac * trackW}
                y={trackY - 22}
                textAnchor="middle"
                fontSize={9}
                fill="#f5222d"
                fontWeight="600"
            >
                Today
            </text>
        </svg>
    );
}

/** Cumulative progress SVG line chart */
function CumulativeChart() {
    const W = 800;
    const H = 180;
    const PADL = 52;
    const PADR = 16;
    const PADT = 16;
    const PADB = 32;
    const chartW = W - PADL - PADR;
    const chartH = H - PADT - PADB;

    const maxVal = Math.max(...CUMULATIVE_DATA, ...CUMULATIVE_TARGET) * 1.05;
    const weeks = CUMULATIVE_DATA.length;

    const toX = (i) => PADL + (i / (weeks - 1)) * chartW;
    const toY = (v) => PADT + chartH - (v / maxVal) * chartH;

    const pathD = (data) =>
        data.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(" ");

    const areaD = (data) =>
        `${pathD(data)} L ${toX(weeks - 1).toFixed(1)},${(PADT + chartH).toFixed(1)} L ${PADL},${(PADT + chartH).toFixed(1)} Z`;

    // Y axis ticks
    const yTicks = [0, 10000, 20000, 30000];

    // X axis ticks (every 4 weeks)
    const xTicks = [0, 4, 8, 12, 16, 20, 24];

    return (
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H }} aria-label="Cumulative items proofread">
            {/* Grid lines */}
            {yTicks.map((v) => (
                <g key={v}>
                    <line
                        x1={PADL} y1={toY(v)} x2={PADL + chartW} y2={toY(v)}
                        stroke="#f0f0f0" strokeWidth={1}
                    />
                    <text x={PADL - 6} y={toY(v) + 4} textAnchor="end" fontSize={9} fill="#8c8c8c">
                        {v === 0 ? "0" : `${v / 1000}k`}
                    </text>
                </g>
            ))}

            {/* X axis ticks */}
            {xTicks.map((i) => (
                <text key={i} x={toX(i)} y={PADT + chartH + 16} textAnchor="middle" fontSize={9} fill="#8c8c8c">
                    Wk {i + 1}
                </text>
            ))}

            {/* Target area fill */}
            <path d={areaD(CUMULATIVE_TARGET)} fill="#1890ff" opacity={0.06} />

            {/* Target line */}
            <path d={pathD(CUMULATIVE_TARGET)} fill="none" stroke="#1890ff" strokeWidth={1.5} strokeDasharray="5 3" />

            {/* Actual area fill */}
            <path d={areaD(CUMULATIVE_DATA)} fill="#52c41a" opacity={0.12} />

            {/* Actual line */}
            <path d={pathD(CUMULATIVE_DATA)} fill="none" stroke="#52c41a" strokeWidth={2} />

            {/* Legend */}
            <g transform={`translate(${PADL + chartW - 160}, ${PADT})`}>
                <line x1={0} y1={8} x2={18} y2={8} stroke="#52c41a" strokeWidth={2} />
                <text x={22} y={12} fontSize={10} fill="#595959">Actual</text>
                <line x1={60} y1={8} x2={78} y2={8} stroke="#1890ff" strokeWidth={1.5} strokeDasharray="4 2" />
                <text x={82} y={12} fontSize={10} fill="#595959">Target</text>
            </g>
        </svg>
    );
}

// ─── Column definitions ───────────────────────────────────────────────────────

const DATASET_COLUMNS = [
    {
        title: "Dataset Name",
        dataIndex: "name",
        key: "name",
        render: (name) => <Text strong>{name}</Text>,
    },
    {
        title: "Experiment",
        dataIndex: "experiment",
        key: "experiment",
        render: (t) => <Text type="secondary">{t}</Text>,
    },
    {
        title: "Total Samples",
        dataIndex: "total",
        key: "total",
        align: "right",
        render: (n) => n.toLocaleString(),
    },
    {
        title: "% Proofread",
        dataIndex: "proofread",
        key: "proofread",
        width: 180,
        render: (pct) => (
            <Space>
                <Progress
                    percent={pct}
                    size="small"
                    style={{ width: 100 }}
                    strokeColor={pct >= 80 ? "#52c41a" : pct >= 40 ? "#faad14" : "#ff4d4f"}
                    showInfo={false}
                />
                <Text style={{ width: 34, textAlign: "right" }}>{pct}%</Text>
            </Space>
        ),
    },
    {
        title: "Status",
        dataIndex: "status",
        key: "status",
        render: statusTag,
    },
    {
        title: "ETA",
        dataIndex: "eta",
        key: "eta",
        render: (eta) => <Text type="secondary">{eta}</Text>,
    },
];

// ─── Main Component ───────────────────────────────────────────────────────────

function AnnotationDashboard() {
    const [filter, setFilter] = useState("all");

    // Derived stats
    const totalSamples = useMemo(
        () => DATASETS.reduce((s, d) => s + d.total, 0),
        []
    );
    const totalProofread = useMemo(
        () =>
            DATASETS.reduce((s, d) => s + Math.round((d.proofread / 100) * d.total), 0),
        []
    );
    const overallPct = Math.round((totalProofread / totalSamples) * 100);
    const activeDatasets = DATASETS.filter((d) => d.status === "in_progress").length;

    // Filtered datasets
    const filteredDatasets = useMemo(() => {
        if (filter === "all") return DATASETS;
        if (filter === "high") return DATASETS.filter((d) => d.priority === "high");
        if (filter === "blocked") return DATASETS.filter((d) => d.status === "blocked");
        return DATASETS;
    }, [filter]);

    const filterBtns = [
        { key: "all", label: "All" },
        { key: "high", label: "High Priority" },
        { key: "blocked", label: "Blocked" },
    ];

    return (
        <div style={{ padding: "0 4px" }}>
            {/* ── Header ── */}
            <div style={{ marginBottom: 20 }}>
                <Title level={4} style={{ margin: 0, color: "#262626" }}>
                    Neural Dataset Proofreading – 6 Months
                </Title>
                <Text type="secondary">
                    {PROJECT_START.format("MMM D, YYYY")} → {PROJECT_END.format("MMM D, YYYY")}
                </Text>
            </div>

            {/* ── KPI Cards ── */}
            <Row gutter={16} style={{ marginBottom: 20 }}>
                <Col span={6}>
                    <Card size="small" bordered={false} style={{ background: "#f6ffed", borderLeft: "4px solid #52c41a" }}>
                        <Statistic
                            title="Total Annotated"
                            value={totalProofread.toLocaleString()}
                            suffix={`/ ${totalSamples.toLocaleString()}`}
                            prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
                            valueStyle={{ color: "#52c41a", fontSize: 18 }}
                        />
                        <Progress percent={overallPct} size="small" showInfo={false} strokeColor="#52c41a" style={{ marginTop: 6 }} />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card size="small" bordered={false} style={{ background: "#e6f7ff", borderLeft: "4px solid #1890ff" }}>
                        <Statistic
                            title="Active Datasets"
                            value={activeDatasets}
                            suffix="/ 6"
                            prefix={<FileTextOutlined style={{ color: "#1890ff" }} />}
                            valueStyle={{ color: "#1890ff", fontSize: 18 }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card size="small" bordered={false} style={{ background: "#f9f0ff", borderLeft: "4px solid #722ed1" }}>
                        <Statistic
                            title="Active Proofreaders"
                            value={8}
                            prefix={<TeamOutlined style={{ color: "#722ed1" }} />}
                            valueStyle={{ color: "#722ed1", fontSize: 18 }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card size="small" bordered={false} style={{ background: "#fff7e6", borderLeft: "4px solid #fa8c16" }}>
                        <Statistic
                            title="Weekly Velocity"
                            value={1420}
                            suffix="items / wk"
                            prefix={<RiseOutlined style={{ color: "#fa8c16" }} />}
                            valueStyle={{ color: "#fa8c16", fontSize: 18 }}
                        />
                    </Card>
                </Col>
            </Row>

            {/* ── Timeline ── */}
            <Card
                size="small"
                title={<Text strong>6-Month Project Timeline</Text>}
                style={{ marginBottom: 20 }}
                bodyStyle={{ paddingTop: 8 }}
            >
                <SixMonthTimeline />
            </Card>

            {/* ── Main content: Table + Right Sidebar ── */}
            <Row gutter={16}>
                {/* Datasets Table */}
                <Col span={17}>
                    <Card
                        size="small"
                        title={<Text strong>Datasets</Text>}
                        extra={
                            <Space>
                                {filterBtns.map((b) => (
                                    <Button
                                        key={b.key}
                                        size="small"
                                        type={filter === b.key ? "primary" : "default"}
                                        shape="round"
                                        onClick={() => setFilter(b.key)}
                                    >
                                        {b.label}
                                    </Button>
                                ))}
                            </Space>
                        }
                        style={{ marginBottom: 20 }}
                    >
                        <Table
                            dataSource={filteredDatasets}
                            columns={DATASET_COLUMNS}
                            pagination={false}
                            size="small"
                            rowKey="key"
                        />
                    </Card>
                </Col>

                {/* Right Sidebar */}
                <Col span={7}>
                    {/* This Week */}
                    <Card
                        size="small"
                        title={
                            <Space>
                                <ThunderboltOutlined style={{ color: "#1890ff" }} />
                                <Text strong>This Week</Text>
                            </Space>
                        }
                        style={{ marginBottom: 12 }}
                    >
                        <Text type="secondary" style={{ fontSize: 12 }}>Items proofread vs. target</Text>
                        <div style={{ marginTop: 10 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                                <Text style={{ fontSize: 12 }}>Completed</Text>
                                <Text strong style={{ fontSize: 12 }}>1,420</Text>
                            </div>
                            <Progress percent={80} strokeColor="#1890ff" size="small" />
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                                <Text type="secondary" style={{ fontSize: 11 }}>Target: 1,750</Text>
                                <Text type="secondary" style={{ fontSize: 11 }}>80%</Text>
                            </div>
                        </div>
                    </Card>

                    {/* At Risk */}
                    <Card
                        size="small"
                        title={
                            <Space>
                                <WarningOutlined style={{ color: "#faad14" }} />
                                <Text strong>At Risk</Text>
                            </Space>
                        }
                        style={{ marginBottom: 12 }}
                    >
                        {AT_RISK.map((item, idx) => (
                            <div key={idx}>
                                {idx > 0 && <Divider style={{ margin: "6px 0" }} />}
                                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                                    {item.icon === "clock" ? (
                                        <ClockCircleOutlined style={{ color: "#faad14", marginTop: 2 }} />
                                    ) : item.icon === "blocked" ? (
                                        <StopOutlined style={{ color: "#ff4d4f", marginTop: 2 }} />
                                    ) : (
                                        <MinusCircleOutlined style={{ color: "#faad14", marginTop: 2 }} />
                                    )}
                                    <div>
                                        <Text strong style={{ fontSize: 12 }}>{item.label}</Text>
                                        <br />
                                        <Text type="secondary" style={{ fontSize: 11 }}>{item.reason}</Text>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </Card>

                    {/* Upcoming Milestones */}
                    <Card
                        size="small"
                        title={
                            <Space>
                                <ClockCircleOutlined style={{ color: "#722ed1" }} />
                                <Text strong>Upcoming Milestones</Text>
                            </Space>
                        }
                    >
                        {UPCOMING_MILESTONES.map((ms, idx) => (
                            <div key={idx}>
                                {idx > 0 && <Divider style={{ margin: "6px 0" }} />}
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <Text style={{ fontSize: 12 }}>{ms.label}</Text>
                                    <Tag color="blue" style={{ fontSize: 10, margin: 0 }}>{ms.date}</Tag>
                                </div>
                            </div>
                        ))}
                    </Card>
                </Col>
            </Row>

            {/* ── Cumulative Progress Chart ── */}
            <Card
                size="small"
                title={<Text strong>Cumulative Items Proofread over 6 Months</Text>}
                style={{ marginBottom: 8 }}
                bodyStyle={{ paddingTop: 8 }}
            >
                <CumulativeChart />
            </Card>
        </div>
    );
}

export default AnnotationDashboard;
