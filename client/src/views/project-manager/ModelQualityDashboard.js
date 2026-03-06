import React, { useState } from "react";
import {
    Card,
    Row,
    Col,
    Statistic,
    Progress,
    Table,
    Tag,
    Button,
    Typography,
    Space,
    Select,
    Divider,
} from "antd";
import {
    LineChartOutlined,
    CheckCircleOutlined,
    WarningOutlined,
    HistoryOutlined,
    ThunderboltOutlined,
    SlidersOutlined,
} from "@ant-design/icons";

const { Title, Text } = Typography;
const { Option } = Select;

// ─── Seed Data ───────────────────────────────────────────────────────────────

const QUALITY_METRICS = {
    accuracy: 94.2,
    precision: 92.5,
    recall: 91.8,
    f1: 92.1,
    agreement: 88.5,
    disagreement: 4.2,
    uncertainty: 2.1,
};

const CONFUSION_MATRIX = [
    { key: "1", actual: "Synapse", predSynapse: 1420, predNonSynapse: 85 },
    { key: "2", actual: "Non-Synapse", predSynapse: 112, predNonSynapse: 3200 },
];

const BATCH_QUALITY = [
    {
        key: "1",
        batch: "Batch #104",
        dataset: "Hippocampus_CA3",
        agreement: 91.2,
        flagged: 12,
        revisionNeeded: 5,
        status: "verified",
    },
    {
        key: "2",
        batch: "Batch #105",
        dataset: "Motor_Cortex_M1",
        agreement: 84.5,
        flagged: 42,
        revisionNeeded: 18,
        status: "needs_review",
    },
    {
        key: "3",
        batch: "Batch #106",
        dataset: "Cerebellum_PC",
        agreement: 89.1,
        flagged: 8,
        revisionNeeded: 2,
        status: "verified",
    },
    {
        key: "4",
        batch: "Batch #107",
        dataset: "Retina_GCL",
        agreement: 72.0,
        flagged: 5,
        revisionNeeded: 22,
        status: "blocked",
    },
];

const TREND_DATA = [82, 84, 85, 83, 86, 88, 87, 89, 91, 93, 94.2];

// ─── Sub-components ──────────────────────────────────────────────────────────

function QualityTrendChart() {
    const W = 800;
    const H = 200;
    const PAD = 40;
    const chartW = W - PAD * 2;
    const chartH = H - PAD;

    const maxVal = 100;
    const minVal = 80; // Zoomed in to show subtle improvements
    const range = maxVal - minVal;

    const toX = (i) => PAD + (i / (TREND_DATA.length - 1)) * chartW;
    const toY = (v) => PAD / 2 + chartH - ((v - minVal) / range) * chartH;

    const pathD = TREND_DATA.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i)},${toY(v)}`).join(" ");

    return (
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H }}>
            {/* Grid lines */}
            {[80, 85, 90, 95, 100].map((v) => (
                <g key={v}>
                    <line
                        x1={PAD}
                        y1={toY(v)}
                        x2={PAD + chartW}
                        y2={toY(v)}
                        stroke="#f0f0f0"
                        strokeWidth={1}
                    />
                    <text x={PAD - 8} y={toY(v) + 4} textAnchor="end" fontSize={10} fill="#8c8c8c">
                        {v}%
                    </text>
                </g>
            ))}

            {/* The Line */}
            <path d={pathD} fill="none" stroke="#1890ff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />

            {/* Area fill */}
            <path
                d={`${pathD} L ${toX(TREND_DATA.length - 1)},${toY(80)} L ${toX(0)},${toY(80)} Z`}
                fill="#1890ff"
                opacity={0.1}
            />

            {/* Points */}
            {TREND_DATA.map((v, i) => (
                <circle key={i} cx={toX(i)} cy={toY(v)} r={4} fill="#1890ff" stroke="#fff" strokeWidth={2} />
            ))}

            {/* Labels */}
            {TREND_DATA.map((v, i) => (
                i % 2 === 0 && (
                    <text key={`label-${i}`} x={toX(i)} y={H - 5} textAnchor="middle" fontSize={10} fill="#8c8c8c">
                        v{i + 1}
                    </text>
                )
            ))}
        </svg>
    );
}

// ─── Column definitions ───────────────────────────────────────────────────────

const BATCH_COLUMNS = [
    {
        title: "Batch",
        dataIndex: "batch",
        key: "batch",
        render: (text) => <Text strong>{text}</Text>,
    },
    {
        title: "Dataset",
        dataIndex: "dataset",
        key: "dataset",
        render: (text) => <Text type="secondary">{text}</Text>,
    },
    {
        title: "IAA Score",
        dataIndex: "agreement",
        key: "agreement",
        render: (val) => (
            <Space>
                <Progress percent={val} size="small" style={{ width: 80 }} strokeColor={val > 85 ? "#52c41a" : "#faad14"} />
                <Text strong>{val}%</Text>
            </Space>
        ),
    },
    {
        title: "Flagged",
        dataIndex: "flagged",
        key: "flagged",
        render: (val) => <Tag color={val > 20 ? "red" : "blue"}>{val} items</Tag>,
    },
    {
        title: "Revision Rate",
        dataIndex: "revisionNeeded",
        key: "revisionNeeded",
        render: (val) => <Text type={val > 10 ? "danger" : "secondary"}>{val}%</Text>,
    },
    {
        title: "Status",
        dataIndex: "status",
        key: "status",
        render: (status) => (
            <Tag color={status === "verified" ? "success" : status === "needs_review" ? "warning" : "error"}>
                {status.toUpperCase().replace("_", " ")}
            </Tag>
        ),
    },
];

// ─── Main Component ───────────────────────────────────────────────────────────

function ModelQualityDashboard() {
    const [modelVersion, setModelVersion] = useState("v3.2");

    return (
        <div style={{ padding: "0 4px" }}>
            {/* ── Header ── */}
            <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
                <Col>
                    <Title level={4} style={{ margin: 0 }}>Model Performance & Data Quality</Title>
                    <Text type="secondary">Monitor model accuracy and annotation consistency</Text>
                </Col>
                <Col>
                    <Space>
                        <Text>Model Version:</Text>
                        <Select value={modelVersion} onChange={setModelVersion} style={{ width: 120 }}>
                            <Option value="v3.2">v3.2 (Latest)</Option>
                            <Option value="v3.1">v3.1</Option>
                            <Option value="v2.8">v2.8</Option>
                        </Select>
                        <Button type="primary" icon={<ThunderboltOutlined />}>Trigger Retrain</Button>
                    </Space>
                </Col>
            </Row>

            {/* ── Main Metrics Gauges ── */}
            <Card size="small" style={{ marginBottom: 20 }}>
                <Row gutter={48} justify="center" align="middle">
                    <Col span={6} style={{ textAlign: "center" }}>
                        <Progress
                            type="circle"
                            percent={QUALITY_METRICS.f1}
                            strokeColor={{ "0%": "#108ee9", "100%": "#87d068" }}
                            format={(pct) => (
                                <div>
                                    <div style={{ fontSize: 24, fontWeight: "bold" }}>{pct}</div>
                                    <div style={{ fontSize: 12, color: "#8c8c8c" }}>F1 Score</div>
                                </div>
                            )}
                        />
                    </Col>
                    <Col span={14}>
                        <Row gutter={24}>
                            <Col span={8}>
                                <Statistic title="Precision" value={QUALITY_METRICS.precision} suffix="%" valueStyle={{ color: "#1890ff" }} />
                            </Col>
                            <Col span={8}>
                                <Statistic title="Recall" value={QUALITY_METRICS.recall} suffix="%" valueStyle={{ color: "#722ed1" }} />
                            </Col>
                            <Col span={8}>
                                <Statistic title="Accuracy" value={QUALITY_METRICS.accuracy} suffix="%" valueStyle={{ color: "#52c41a" }} />
                            </Col>
                        </Row>
                        <Divider style={{ margin: "12px 0" }} />
                        <Row gutter={24}>
                            <Col span={8}>
                                <Statistic title="Agreement" value={QUALITY_METRICS.agreement} suffix="%" prefix={<CheckCircleOutlined />} />
                            </Col>
                            <Col span={8}>
                                <Statistic title="Disagreement" value={QUALITY_METRICS.disagreement} suffix="%" prefix={<WarningOutlined style={{ color: "#faad14" }} />} />
                            </Col>
                            <Col span={8}>
                                <Statistic title="Avg Uncertainty" value={QUALITY_METRICS.uncertainty} suffix="%" prefix={<SlidersOutlined />} />
                            </Col>
                        </Row>
                    </Col>
                </Row>
            </Card>

            <Row gutter={16}>
                {/* Quality Trend */}
                <Col span={16}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <LineChartOutlined />
                                <Text strong>Model Performance Trend (Last 12 Iterations)</Text>
                            </Space>
                        }
                        extra={<Button size="small" type="link">View Detailed Logs</Button>}
                        style={{ marginBottom: 20 }}
                    >
                        <QualityTrendChart />
                    </Card>
                </Col>

                {/* Confusion Matrix */}
                <Col span={8}>
                    <Card
                        size="small"
                        title={<Text strong>Confusion Matrix (v3.2)</Text>}
                        style={{ marginBottom: 20 }}
                    >
                        <div style={{ padding: "8px 0" }}>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, textAlign: "center" }}>
                                <div />
                                <Text strong style={{ fontSize: 11 }}>Pred Syn</Text>
                                <Text strong style={{ fontSize: 11 }}>Pred Non</Text>

                                <Text strong style={{ textAlign: "right", fontSize: 11 }}>Act Syn</Text>
                                <div style={{ background: "#f6ffed", padding: 8, border: "1px solid #d9f7be" }}>
                                    <Text strong>1,420</Text>
                                    <div style={{ fontSize: 9, color: "#52c41a" }}>TP</div>
                                </div>
                                <div style={{ background: "#fff1f0", padding: 8, border: "1px solid #ffccc7" }}>
                                    <Text>85</Text>
                                    <div style={{ fontSize: 9, color: "#f5222d" }}>FN</div>
                                </div>

                                <Text strong style={{ textAlign: "right", fontSize: 11 }}>Act Non</Text>
                                <div style={{ background: "#fff1f0", padding: 8, border: "1px solid #ffccc7" }}>
                                    <Text>112</Text>
                                    <div style={{ fontSize: 9, color: "#f5222d" }}>FP</div>
                                </div>
                                <div style={{ background: "#f6ffed", padding: 8, border: "1px solid #d9f7be" }}>
                                    <Text strong>3,200</Text>
                                    <div style={{ fontSize: 9, color: "#52c41a" }}>TN</div>
                                </div>
                            </div>
                            <div style={{ marginTop: 16, textAlign: "center" }}>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                    *Based on evaluation dataset: 4,817 samples
                                </Text>
                            </div>
                        </div>
                    </Card>
                </Col>
            </Row>

            {/* Batch Data Quality Table */}
            <Card
                size="small"
                title={
                    <Space>
                        <HistoryOutlined />
                        <Text strong>Data Quality Log (Per Batch)</Text>
                    </Space>
                }
            >
                <Table
                    dataSource={BATCH_QUALITY}
                    columns={BATCH_COLUMNS}
                    pagination={false}
                    size="small"
                />
            </Card>
        </div>
    );
}

export default ModelQualityDashboard;
