import React, { useMemo } from "react";
import {
  Alert,
  Card,
  Table,
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
  CopyOutlined,
  ThunderboltOutlined,
  EditOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useProjectManager } from "../../contexts/ProjectManagerContext";

const { Title, Text } = Typography;
const { TextArea } = Input;

// ─── Sparkline trend data for the last 8 weeks (attainment percentages) ──────

const PERFORMANCE_TRENDS = {
  1: [98, 102, 100, 95, 105, 101, 100, 99],
  2: [90, 92, 88, 85, 90, 94, 91, 89],
  3: [70, 75, 65, 80, 72, 60, 55, 62],
  4: [100, 105, 110, 100, 102, 108, 104, 106],
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
  const {
    quotaData,
    datasets,
    msgPreview,
    setQuotaData,
    setMsgPreview,
    saving,
    resetData,
    isAdmin,
    isWorker,
  } = useProjectManager();

  const handleUpdateQuota = (key, day, val) => {
    const updated = quotaData.map((item) =>
      item.key === key ? { ...item, [day]: val } : item,
    );
    setQuotaData(updated);
  };

  const handleAutoAllocate = () => {
    const datasetPriorityByName = new Map(
      (datasets || []).map((dataset) => [dataset.name, dataset.priority]),
    );
    const weeklyTotal = quotaData.reduce(
      (sum, row) =>
        sum +
        row.mon +
        row.tue +
        row.wed +
        row.thu +
        row.fri +
        row.sat +
        row.sun,
      0,
    );
    const scoredRows = quotaData.map((row) => {
      const currentTarget =
        row.mon + row.tue + row.wed + row.thu + row.fri + row.sat + row.sun;
      const currentActual =
        (row.actualMon || 0) +
        (row.actualTue || 0) +
        (row.actualWed || 0) +
        (row.actualThu || 0) +
        (row.actualFri || 0) +
        (row.actualSat || 0) +
        (row.actualSun || 0);
      const datasetWeight = (row.datasets || []).reduce((sum, datasetName) => {
        return (
          sum +
          (datasetPriorityByName.get(datasetName) === "high" ? 1.35 : 1.0)
        );
      }, 0);
      const normalizedDatasetWeight = row.datasets?.length
        ? datasetWeight / row.datasets.length
        : 1;
      const score =
        Math.max(currentActual, Math.max(currentTarget, 1) * 0.85, 1) *
        normalizedDatasetWeight;
      return { row, currentTarget, score };
    });
    const totalScore =
      scoredRows.reduce((sum, entry) => sum + entry.score, 0) || 1;
    const dayKeys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

    const updated = scoredRows.map(({ row, score }) => {
      const nextRow = { ...row };
      const weeklyTarget = Math.max(
        100,
        Math.round((weeklyTotal * (score / totalScore)) / 10) * 10,
      );
      const currentDayTotal = dayKeys.reduce((sum, day) => sum + row[day], 0);
      const activeDays = dayKeys.filter((day) => row[day] > 0);
      const distributionDays =
        activeDays.length > 0 ? activeDays : ["mon", "tue", "wed", "thu", "fri"];
      let remaining = weeklyTarget;

      distributionDays.forEach((day, index) => {
        let nextValue;
        if (index === distributionDays.length - 1) {
          nextValue = remaining;
        } else {
          const weight =
            currentDayTotal > 0 ? row[day] / currentDayTotal : 1 / distributionDays.length;
          nextValue = Math.round((weeklyTarget * weight) / 10) * 10;
          remaining -= nextValue;
        }
        nextRow[day] = Math.max(0, nextValue);
      });

      dayKeys
        .filter((day) => !distributionDays.includes(day))
        .forEach((day) => {
          nextRow[day] = 0;
        });

      return nextRow;
    });

    setQuotaData(updated);
    message.success(
      "Rebalanced weekly targets using recent throughput and dataset priority.",
    );
  };

  const handleCopyDraft = async () => {
    try {
      await navigator.clipboard.writeText(msgPreview);
      message.success("Communication draft copied to clipboard.");
    } catch (error) {
      message.error("Failed to copy draft to clipboard.");
    }
  };

  // Day columns
  const dayCols = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map(
    (day) => ({
      title: day.charAt(0).toUpperCase() + day.slice(1),
      dataIndex: day,
      key: day,
      width: 100,
      render: (val, record) => {
        const actual =
          record[`actual${day.charAt(0).toUpperCase() + day.slice(1)}`];
        const attainment = val > 0 ? Math.round((actual / val) * 100) : 100;
        return (
          <div style={{ padding: "8px 4px", borderRadius: 4 }}>
            <div style={{ marginBottom: 4 }}>
              <Text
                type="secondary"
                style={{
                  fontSize: 9,
                  display: "block",
                  textTransform: "uppercase",
                }}
              >
                Target
              </Text>
              <InputNumber
                size="small"
                value={val}
                onChange={(v) => handleUpdateQuota(record.key, day, v)}
                disabled={isWorker}
                style={{
                  width: "100%",
                  fontWeight: "bold",
                  background: "#e6f7ff",
                  borderRadius: 4,
                  border: "1px solid #91d5ff",
                }}
                controls={false}
              />
            </div>
            <div>
              <Text
                type="secondary"
                style={{
                  fontSize: 9,
                  display: "block",
                  textTransform: "uppercase",
                }}
              >
                Actual
              </Text>
              <Tooltip title={`Attainment: ${attainment}%`}>
                <Tag
                  color={getAttainmentColor(attainment)}
                  style={{
                    width: "100%",
                    margin: 0,
                    textAlign: "center",
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: "600",
                  }}
                >
                  {actual}
                </Tag>
              </Tooltip>
            </div>
          </div>
        );
      },
    }),
  );

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
          <div style={{ fontSize: 10, color: "#8c8c8c" }}>
            {record.datasets.join(", ")}
          </div>
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
        const targetTotal =
          record.mon +
          record.tue +
          record.wed +
          record.thu +
          record.fri +
          record.sat +
          record.sun;
        const actualTotal =
          record.actualMon +
          record.actualTue +
          record.actualWed +
          record.actualThu +
          record.actualFri +
          record.actualSat +
          record.actualSun;
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
      },
    },
    {
      title: "8-Wk Trend",
      key: "trend",
      width: 120,
      fixed: "right",
      render: (_, record) => (
        <Sparkline data={PERFORMANCE_TRENDS[record.key] || []} />
      ),
    },
  ];

  // Dynamic Calculations for Summary
  const totals = useMemo(() => {
    return quotaData.reduce(
      (acc, row) => {
        acc.target +=
          row.mon + row.tue + row.wed + row.thu + row.fri + row.sat + row.sun;
        acc.actual +=
          (row.actualMon || 0) +
          (row.actualTue || 0) +
          (row.actualWed || 0) +
          (row.actualThu || 0) +
          (row.actualFri || 0) +
          (row.actualSat || 0) +
          (row.actualSun || 0);
        return acc;
      },
      { target: 0, actual: 0 },
    );
  }, [quotaData]);

  const globalUtilization =
    totals.target > 0 ? Math.round((totals.actual / totals.target) * 100) : 0;
  const remainingBuffer = Math.max(0, totals.target - totals.actual);

  return (
    <div style={{ padding: "0 4px" }}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Live planning surface"
        description="Quota targets persist to the Project Manager JSON. This view currently supports one active plan only; historical week switching and outbound dispatch are not wired."
      />

      {/* ── Header ── */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            {isWorker ? "My Weekly Quota" : "Weekly Quota Management"}
          </Title>
          <Text type="secondary">
            {isWorker
              ? "Manager-defined targets and your current attainment"
              : "Plan targets and track capacity utilization · auto-saved to JSON"}
            {saving && (
              <>
                {" "}
                · <Spin size="small" style={{ marginLeft: 6 }} /> saving…
              </>
            )}
          </Text>
        </Col>
        <Col>
          <Space>
            <Tag color="blue">Single active plan</Tag>
            {isAdmin && (
              <Button
                type="primary"
                ghost
                icon={<ThunderboltOutlined />}
                onClick={handleAutoAllocate}
                style={{ borderRadius: 6 }}
              >
                Rebalance Targets
              </Button>
            )}
            {isAdmin && (
              <Popconfirm
                title="Start a fresh project?"
                description="This will clear tracked volumes and restore a blank planning state for the active metadata file."
                onConfirm={resetData}
                okText="Start Fresh"
                cancelText="Cancel"
                okButtonProps={{ danger: true }}
              >
                <Button
                  icon={<ReloadOutlined />}
                  danger
                  style={{ borderRadius: 6 }}
                >
                  Start Fresh Project
                </Button>
              </Popconfirm>
            )}
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
            <Tag color="blue" style={{ borderRadius: 4 }}>
              Week 10 (Current)
            </Tag>
          </Space>
        }
        extra={
          <Text type="secondary" style={{ fontSize: 12 }}>
            {isAdmin
              ? "Blue cells are editable manager targets."
              : "Targets are manager-controlled in this build."}
          </Text>
        }
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
          <Card
            size="small"
            title={<Text strong>Capacity Summary</Text>}
            style={{ borderRadius: 8 }}
          >
            <div style={{ padding: "8px 0" }}>
              <Tooltip title="Total capacity utilization based on current active targets">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Global Utilization
                </Text>
                <Progress
                  percent={globalUtilization}
                  status="active"
                  strokeColor={getAttainmentColor(globalUtilization)}
                />
              </Tooltip>
              <Divider style={{ margin: "12px 0" }} />
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Text type="secondary">Total Weekly Target</Text>
                <Text strong>{totals.target.toLocaleString()} points</Text>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 8,
                }}
              >
                <Text type="secondary">Actual points so far</Text>
                <Text strong>{totals.actual.toLocaleString()} points</Text>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 8,
                }}
              >
                <Text type="secondary">Remaining to target</Text>
                <Text
                  strong
                  style={{ color: remainingBuffer > 0 ? "#faad14" : "#52c41a" }}
                >
                  {remainingBuffer.toLocaleString()}
                </Text>
              </div>
            </div>
          </Card>
        </Col>

        {isAdmin && (
          <Col span={16}>
            <Card
              size="small"
              title={
                <Text strong>
                  <EditOutlined /> Team Communication Draft
                </Text>
              }
              extra={
                <Button
                  type="primary"
                  icon={<CopyOutlined />}
                  onClick={handleCopyDraft}
                >
                  Copy Draft
                </Button>
              }
            >
              <TextArea
                rows={6}
                value={msgPreview}
                onChange={(e) => setMsgPreview(e.target.value)}
                style={{
                  fontFamily: "monospace",
                  fontSize: 13,
                  background: "#fafafa",
                }}
              />
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  This is a saved draft only. No outbound dispatch integration is
                  wired yet.
                </Text>
              </div>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
}

export default QuotaManagement;
