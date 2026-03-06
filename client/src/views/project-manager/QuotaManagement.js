import React, { useState, useMemo } from "react";
import {
    Card,
    Table,
    DatePicker,
    Button,
    Input,
    InputNumber,
    Row,
    Col,
    Typography,
    Space,
    Tag,
    Divider,
    Progress,
    Tooltip,
    message,
} from "antd";
import {
    ScheduleOutlined,
    SendOutlined,
    ThunderboltOutlined,
    LeftOutlined,
    RightOutlined,
    EditOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import weekday from "dayjs/plugin/weekday";
import localeData from "dayjs/plugin/localeData";

dayjs.extend(weekday);
dayjs.extend(localeData);

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

// ─── Seed Data ───────────────────────────────────────────────────────────────

const QUOTA_DATA = [
    {
        key: "1",
        name: "Alex Rivera",
        datasets: ["Hippocampus_CA3", "Motor_Cortex_M1"],
        mon: 300, tue: 300, wed: 300, thu: 300, fri: 300, sat: 150, sun: 100,
        actualMon: 310, actualTue: 290, actualWed: 320, actualThu: 280, actualFri: 300, actualSat: 160, actualSun: 90,
    },
    {
        key: "2",
        name: "Jordan Smith",
        datasets: ["Cerebellum_PC"],
        mon: 250, tue: 250, wed: 250, thu: 250, fri: 250, sat: 0, sun: 0,
        actualMon: 240, actualTue: 260, actualWed: 230, actualThu: 250, actualFri: 220, actualSat: 0, actualSun: 0,
    },
    {
        key: "3",
        name: "Sam Taylor",
        datasets: ["Retina_GCL"],
        mon: 200, tue: 200, wed: 200, thu: 200, fri: 200, sat: 250, sun: 250,
        actualMon: 180, actualTue: 190, actualWed: 170, actualThu: 210, actualFri: 200, actualSat: 100, actualSun: 0,
    },
    {
        key: "4",
        name: "Casey Chen",
        datasets: ["Visual_Cortex_V1"],
        mon: 240, tue: 240, wed: 240, thu: 240, fri: 240, sat: 0, sun: 0,
        actualMon: 250, actualTue: 260, actualWed: 270, actualThu: 240, actualFri: 230, actualSat: 0, actualSun: 0,
    },
];

// Sparkline trend data for the last 8 weeks (attainment percentages)
const PERFORMANCE_TRENDS = {
    "1": [98, 102, 100, 95, 105, 101, 100, 99],
    "2": [90, 92, 88, 85, 90, 94, 91, 89],
    "3": [70, 75, 65, 80, 72, 60, 55, 62],
    "4": [100, 105, 110, 100, 102, 108, 104, 106],
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getAttainmentColor(percent) {
    if (percent >= 100) return "#52c41a"; // success
    if (percent >= 75) return "#faad14"; // warning
    return "#f5222d"; // error
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function Sparkline({ data }) {
    const W = 100;
    const H = 20;
    const gap = 2;
    const barW = (W - (data.length - 1) * gap) / data.length;

    return (
        <svg width={W} height={H} style={{ display: "block" }}>
            {data.map((v, i) => {
                const h = (v / 120) * H; // scaled to 120% max
                return (
                    <rect
                        key={i}
                        x={i * (barW + gap)}
                        y={H - h}
                        width={barW}
                        height={h}
                        fill={getAttainmentColor(v)}
                        rx={1}
                    />
                );
            })}
        </svg>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

function QuotaManagement() {
    const [data, setData] = useState(QUOTA_DATA);
    const [selectedWeek, setSelectedWeek] = useState(dayjs().startOf("week"));
    const [msgPreview, setMsgPreview] = useState(
        "Hi Team,\n\nI've just assigned the quotas for the upcoming week. Please review your targets in the dashboard. Our goal for this week is to maintain 95%+ accuracy while meeting the sample volume targets.\n\nGood luck!"
    );

    const handleUpdateQuota = (key, day, val) => {
        const newData = data.map(item => {
            if (item.key === key) {
                return { ...item, [day]: val };
            }
            return item;
        });
        setData(newData);
    };

    const handleAutoAllocate = () => {
        message.loading("Calculating optimal distribution...", 1.5).then(() => {
            message.success("Quotas auto-allocated based on user capacity and dataset priority.");
        });
    };

    const handleSendQuotas = () => {
        message.success("Weekly quotas dispatched to 4 proofreaders.");
    };

    const columns = [
        {
            title: "Name",
            dataIndex: "name",
            key: "name",
            width: 150,
            render: (text, record) => (
                <div>
                    <Text strong>{text}</Text>
                    <div style={{ fontSize: 10, color: "#8c8c8c" }}>
                        {record.datasets.join(", ")}
                    </div>
                </div>
            )
        },
        {
            title: "Target / Actual",
            children: [
                { title: "Mon", dataIndex: "mon", key: "mon", width: 80 },
                { title: "Tue", dataIndex: "tue", key: "tue", width: 80 },
                { title: "Wed", dataIndex: "wed", key: "wed", width: 80 },
                { title: "Thu", dataIndex: "thu", key: "thu", width: 80 },
                { title: "Fri", dataIndex: "fri", key: "fri", width: 80 },
                { title: "Sat", dataIndex: "sat", key: "sat", width: 80 },
                { title: "Sun", dataIndex: "sun", key: "sun", width: 80 },
            ],
            render: (_, record) => {
                // This is a complex render because we want Target (editable) over Actual
                // For simplicity in this mock, we'll just show the target as an input for the day selected
                // but Ant Design tables handle nested children differently.
                // We'll map the days below for clarity.
            }
        },
        {
            title: "Weekly Total",
            key: "total",
            width: 120,
            align: "right",
            render: (_, record) => {
                const targetTotal = record.mon + record.tue + record.wed + record.thu + record.fri + record.sat + record.sun;
                const actualTotal = record.actualMon + record.actualTue + record.actualWed + record.actualThu + record.actualFri + record.actualSat + record.actualSun;
                const attainment = Math.round((actualTotal / targetTotal) * 100);
                return (
                    <div style={{ textAlign: "right" }}>
                        <Text strong>{actualTotal.toLocaleString()}</Text>
                        <Text type="secondary" style={{ fontSize: 11 }}> / {targetTotal.toLocaleString()}</Text>
                        <br />
                        <Tag color={getAttainmentColor(attainment)} style={{ margin: 0, fontSize: 10 }}>
                            {attainment}%
                        </Tag>
                    </div>
                );
            }
        },
        {
            title: "Capacity",
            key: "capacity",
            width: 100,
            render: (_, record) => {
                const total = record.mon + record.tue + record.wed + record.thu + record.fri + record.sat + record.sun;
                const load = Math.min(100, Math.round((total / 2000) * 100)); // Assuming 2000 is max capacity
                return <Progress percent={load} size="small" status={load > 90 ? "exception" : "active"} />;
            }
        },
        {
            title: "8-Week Trend",
            key: "trend",
            width: 120,
            render: (_, record) => <Sparkline data={PERFORMANCE_TRENDS[record.key] || []} />
        }
    ];

    // Manual mapping of day columns to enable per-cell editing UI
    const dayCols = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map(day => ({
        title: day.charAt(0).toUpperCase() + day.slice(1),
        dataIndex: day,
        key: day,
        width: 80,
        render: (val, record) => {
            const actual = record[`actual${day.charAt(0).toUpperCase() + day.slice(1)}`];
            const attainment = val > 0 ? Math.round((actual / val) * 100) : 100;
            return (
                <div style={{ padding: "4px 0" }}>
                    <InputNumber
                        size="small"
                        value={val}
                        onChange={(v) => handleUpdateQuota(record.key, day, v)}
                        bordered={false}
                        style={{ width: "100%", fontWeight: "bold", padding: 0 }}
                        controls={false}
                    />
                    <Tooltip title={`Actual: ${actual}`}>
                        <Text style={{
                            fontSize: 10,
                            color: getAttainmentColor(attainment),
                            display: "block",
                            borderTop: "1px solid #f0f0f0",
                            marginTop: 2
                        }}>
                            {actual} ({attainment}%)
                        </Text>
                    </Tooltip>
                </div>
            );
        }
    }));

    const finalColumns = [
        {
            title: "Proofreader",
            dataIndex: "name",
            key: "name",
            fixed: "left",
            width: 160,
            render: (text, record) => (
                <div>
                    <Text strong>{text}</Text>
                    <div style={{ fontSize: 10, color: "#8c8c8c" }}>{record.datasets.join(", ")}</div>
                </div>
            )
        },
        ...dayCols,
        {
            title: "Weekly Summary",
            key: "total",
            width: 140,
            fixed: "right",
            render: (_, record) => {
                const targetTotal = record.mon + record.tue + record.wed + record.thu + record.fri + record.sat + record.sun;
                const actualTotal = record.actualMon + record.actualTue + record.actualWed + record.actualThu + record.actualFri + record.actualSat + record.actualSun;
                const attainment = Math.round((actualTotal / targetTotal) * 100);
                return (
                    <div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <Text strong>{actualTotal}</Text>
                            <Text type="secondary">/ {targetTotal}</Text>
                        </div>
                        <Progress
                            percent={attainment}
                            size={[100, 4]}
                            strokeColor={getAttainmentColor(attainment)}
                            showInfo={false}
                        />
                    </div>
                );
            }
        },
        {
            title: "8-Wk Trend",
            key: "trend",
            width: 120,
            fixed: "right",
            render: (_, record) => <Sparkline data={PERFORMANCE_TRENDS[record.key] || []} />
        }
    ];

    return (
        <div style={{ padding: "0 4px" }}>
            {/* ── Header ── */}
            <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
                <Col>
                    <Title level={4} style={{ margin: 0 }}>Weekly Quota Management</Title>
                    <Text type="secondary">Plan targets and track capacity utilization</Text>
                </Col>
                <Col>
                    <Space>
                        <Button icon={<LeftOutlined />} onClick={() => setSelectedWeek(selectedWeek.subtract(1, "week"))} />
                        <DatePicker
                            picker="week"
                            value={selectedWeek}
                            onChange={setSelectedWeek}
                            allowClear={false}
                            format="MMM D, YYYY"
                            style={{ width: 220 }}
                        />
                        <Button icon={<RightOutlined />} onClick={() => setSelectedWeek(selectedWeek.add(1, "week"))} />
                        <Button type="primary" ghost icon={<ThunderboltOutlined />} onClick={handleAutoAllocate}>
                            Auto-Allocate
                        </Button>
                    </Space>
                </Col>
            </Row>

            {/* ── Quota Table ── */}
            <Card
                size="small"
                bodyStyle={{ padding: 0 }}
                title={
                    <Space>
                        <ScheduleOutlined />
                        <Text strong>Targets vs Actuals</Text>
                        <Tag color="blue">Week 10 (Current)</Tag>
                    </Space>
                }
                extra={<Text type="secondary" style={{ fontSize: 12 }}>Click values to edit targets</Text>}
                style={{ marginBottom: 20 }}
            >
                <Table
                    dataSource={data}
                    columns={finalColumns}
                    pagination={false}
                    size="small"
                    scroll={{ x: 1200 }}
                    bordered
                />
            </Card>

            <Row gutter={16}>
                {/* Statistics Component (Small subset) */}
                <Col span={8}>
                    <Card size="small" title={<Text strong>Capacity Summary</Text>}>
                        <div style={{ padding: "8px 0" }}>
                            <Tooltip title="Total capacity utilization across all proofreaders">
                                <Text type="secondary">Global Utilization</Text>
                                <Progress percent={76} status="active" />
                            </Tooltip>
                            <Divider style={{ margin: "12px 0" }} />
                            <div style={{ display: "flex", justifyContent: "space-between" }}>
                                <Text type="secondary">Total Weekly Goal</Text>
                                <Text strong>7,200 samples</Text>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                                <Text type="secondary">Allocated So Far</Text>
                                <Text strong>5,480 samples</Text>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                                <Text type="secondary">Remaining Buffer</Text>
                                <Text strong style={{ color: "#52c41a" }}>1,720 (24%)</Text>
                            </div>
                        </div>
                    </Card>
                </Col>

                {/* Communication Preview */}
                <Col span={16}>
                    <Card
                        size="small"
                        title={<Text strong><EditOutlined /> Team Communication Preview</Text>}
                        extra={
                            <Button type="primary" icon={<SendOutlined />} onClick={handleSendQuotas}>
                                Send Quotas
                            </Button>
                        }
                    >
                        <TextArea
                            rows={6}
                            value={msgPreview}
                            onChange={e => setMsgPreview(e.target.value)}
                            style={{ fontFamily: "monospace", fontSize: 13, background: "#fafafa" }}
                        />
                        <div style={{ marginTop: 8 }}>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                                This message will be sent to 4 proofreaders via the internal notification system.
                            </Text>
                        </div>
                    </Card>
                </Col>
            </Row>
        </div>
    );
}

export default QuotaManagement;
