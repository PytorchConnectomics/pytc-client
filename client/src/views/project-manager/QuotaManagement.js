import React, { useMemo } from "react";
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
    Popconfirm,
    Spin,
} from "antd";
import {
    ScheduleOutlined,
    SendOutlined,
    ThunderboltOutlined,
    LeftOutlined,
    RightOutlined,
    EditOutlined,
    ReloadOutlined,
    SaveOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import weekday from "dayjs/plugin/weekday";
import localeData from "dayjs/plugin/localeData";
import { useState } from "react";
import { useProjectManager } from "../../contexts/ProjectManagerContext";

dayjs.extend(weekday);
dayjs.extend(localeData);

const { Title, Text } = Typography;
const { TextArea } = Input;

// ─── Sparkline trend data for the last 8 weeks (attainment percentages) ──────

const PERFORMANCE_TRENDS = {
    "1": [98, 102, 100, 95, 105, 101, 100, 99],
    "2": [90, 92, 88, 85, 90, 94, 91, 89],
    "3": [70, 75, 65, 80, 72, 60, 55, 62],
    "4": [100, 105, 110, 100, 102, 108, 104, 106],
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getAttainmentColor(percent) {
    if (percent >= 100) return "#52c41a";
    if (percent >= 75) return "#faad14";
    return "#f5222d";
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
                const h = (v / 120) * H;
                return (
                    <rect key={i} x={i * (barW + gap)} y={H - h}
                        width={barW} height={h} fill={getAttainmentColor(v)} rx={1} />
                );
            })}
        </svg>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

function QuotaManagement() {
    const {
        quotaData,
        msgPreview,
        setQuotaData,
        setMsgPreview,
        saving,
        resetData,
    } = useProjectManager();

    const [selectedWeek, setSelectedWeek] = useState(dayjs().startOf("week"));

    const handleUpdateQuota = (key, day, val) => {
        const updated = quotaData.map(item =>
            item.key === key ? { ...item, [day]: val } : item
        );
        setQuotaData(updated);
    };

    const handleAutoAllocate = () => {
        message.loading("Calculating optimal distribution...", 1.5).then(() => {
            message.success("Quotas auto-allocated based on user capacity and dataset priority.");
        });
    };

    const handleSendQuotas = () => {
        message.success("Weekly quotas dispatched to proofreaders.");
    };

    // Day columns
    const dayCols = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map(day => ({
        title: day.charAt(0).toUpperCase() + day.slice(1),
        dataIndex: day,
        key: day,
        width: 100,
        render: (val, record) => {
            const actual = record[`actual${day.charAt(0).toUpperCase() + day.slice(1)}`];
            const attainment = val > 0 ? Math.round((actual / val) * 100) : 100;
            return (
                <div style={{ padding: "8px 4px", borderRadius: 4 }}>
                    <div style={{ marginBottom: 4 }}>
                        <Text type="secondary" style={{ fontSize: 9, display: "block", textTransform: "uppercase" }}>Target</Text>
                        <InputNumber
                            size="small"
                            value={val}
                            onChange={(v) => handleUpdateQuota(record.key, day, v)}
                            style={{ 
                                width: "100%", 
                                fontWeight: "bold", 
                                background: "#e6f7ff",
                                borderRadius: 4,
                                border: "1px solid #91d5ff"
                            }}
                            controls={false}
                        />
                    </div>
                    <div>
                        <Text type="secondary" style={{ fontSize: 9, display: "block", textTransform: "uppercase" }}>Actual</Text>
                        <Tooltip title={`Attainment: ${attainment}%`}>
                            <Tag 
                                color={getAttainmentColor(attainment)} 
                                style={{ width: "100%", margin: 0, textAlign: "center", borderRadius: 4, fontSize: 11, fontWeight: "600" }}
                            >
                                {actual}
                            </Tag>
                        </Tooltip>
                    </div>
                </div>
            );
        },
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
            ),
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
                        <Progress percent={attainment} size={[100, 4]} strokeColor={getAttainmentColor(attainment)} showInfo={false} />
                    </div>
                );
            },
        },
        {
            title: "8-Wk Trend",
            key: "trend",
            width: 120,
            fixed: "right",
            render: (_, record) => <Sparkline data={PERFORMANCE_TRENDS[record.key] || []} />,
        },
    ];

    // Dynamic Calculations for Summary
    const totals = useMemo(() => {
        return quotaData.reduce((acc, row) => {
            acc.target += (row.mon + row.tue + row.wed + row.thu + row.fri + row.sat + row.sun);
            acc.actual += ((row.actualMon || 0) + (row.actualTue || 0) + (row.actualWed || 0) + 
                          (row.actualThu || 0) + (row.actualFri || 0) + (row.actualSat || 0) + (row.actualSun || 0));
            return acc;
        }, { target: 0, actual: 0 });
    }, [quotaData]);

    const globalUtilization = totals.target > 0 ? Math.round((totals.actual / totals.target) * 100) : 0;
    const remainingBuffer = Math.max(0, totals.target - totals.actual);

    return (
        <div style={{ padding: "0 4px" }}>
            {/* ── Header ── */}
            <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
                <Col>
                    <Title level={4} style={{ margin: 0 }}>Weekly Quota Management</Title>
                    <Text type="secondary">
                        Plan targets and track capacity utilization · <b>Real-time Sync</b>
                        {saving && <> · <Spin size="small" style={{ marginLeft: 6 }} /> saving…</>}
                    </Text>
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
                            style={{ width: 220, borderRadius: 6 }}
                        />
                        <Button icon={<RightOutlined />} onClick={() => setSelectedWeek(selectedWeek.add(1, "week"))} />
                        <Button type="primary" ghost icon={<ThunderboltOutlined />} onClick={handleAutoAllocate} style={{ borderRadius: 6 }}>
                            Auto-Allocate
                        </Button>
                        <Popconfirm
                            title="Reset all quota data to defaults?"
                            description="This will overwrite server data with original seed values."
                            onConfirm={resetData}
                            okText="Reset"
                            cancelText="Cancel"
                            okButtonProps={{ danger: true }}
                        >
                            <Button icon={<ReloadOutlined />} danger style={{ borderRadius: 6 }}>Reset to Defaults</Button>
                        </Popconfirm>
                    </Space>
                </Col>
            </Row>

            {/* ── Quota Table ── */}
            <Card
                size="small"
                bodyStyle={{ padding: 0 }}
                title={
                    <Space>
                        <ScheduleOutlined style={{ color: "#1890ff" }} />
                        <Text strong>Targets vs Actuals</Text>
                        <Tag color="blue" style={{ borderRadius: 4 }}>Week 10 (Current)</Tag>
                    </Space>
                }
                extra={<Text type="secondary" style={{ fontSize: 12 }}>Input numbers in blue cells to update targets instantly.</Text>}
                style={{ marginBottom: 20, borderRadius: 8, overflow: "hidden" }}
            >
                <Table
                    dataSource={quotaData}
                    columns={finalColumns}
                    pagination={false}
                    size="small"
                    scroll={{ x: 1200 }}
                    bordered
                />
            </Card>

            <Row gutter={16}>
                {/* Capacity Summary */}
                <Col span={8}>
                    <Card size="small" title={<Text strong>Capacity Summary</Text>} style={{ borderRadius: 8 }}>
                        <div style={{ padding: "8px 0" }}>
                            <Tooltip title="Total capacity utilization based on current active targets">
                                <Text type="secondary" style={{ fontSize: 12 }}>Global Utilization</Text>
                                <Progress percent={globalUtilization} status="active" strokeColor={getAttainmentColor(globalUtilization)} />
                            </Tooltip>
                            <Divider style={{ margin: "12px 0" }} />
                            <div style={{ display: "flex", justifyContent: "space-between" }}>
                                <Text type="secondary">Total Weekly Target</Text>
                                <Text strong>{totals.target.toLocaleString()} points</Text>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                                <Text type="secondary">Actual points so far</Text>
                                <Text strong>{totals.actual.toLocaleString()} points</Text>
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                                <Text type="secondary">Remaining to target</Text>
                                <Text strong style={{ color: remainingBuffer > 0 ? "#faad14" : "#52c41a" }}>
                                    {remainingBuffer.toLocaleString()}
                                </Text>
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
                                This message will be sent to proofreaders via the internal notification system.
                            </Text>
                        </div>
                    </Card>
                </Col>
            </Row>
        </div>
    );
}

export default QuotaManagement;
