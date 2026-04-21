import React, { useState, useMemo } from "react";
import {
  Alert,
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
  DatabaseOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";

import { useProjectManager } from "../../contexts/ProjectManagerContext";

const { Title, Text } = Typography;

const PROJECT_START = dayjs("2025-10-01");
const PROJECT_END = dayjs("2026-03-31");

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
function SixMonthTimeline({ milestones }) {
  const W = 900;
  const H = 80;
  const PAD = 40;
  const trackY = 48;
  const trackW = W - PAD * 2;

  const months = [];
  let cur = PROJECT_START.startOf("month");
  while (cur.isBefore(PROJECT_END) || cur.isSame(PROJECT_END, "month")) {
    months.push(cur);
    cur = cur.add(1, "month");
  }

  const todayFrac = dateToFrac(dayjs("2026-03-20"));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", height: H }}
      aria-label="6-month annotation project timeline"
    >
      <rect
        x={PAD}
        y={trackY - 4}
        width={trackW}
        height={8}
        rx={4}
        fill="#e8e8e8"
      />
      <rect
        x={PAD}
        y={trackY - 4}
        width={trackW * todayFrac}
        height={8}
        rx={4}
        fill="#1890ff"
        opacity={0.3}
      />
      {months.map((m) => {
        const x = PAD + dateToFrac(m) * trackW;
        return (
          <g key={m.format("YYYY-MM")}>
            <line
              x1={x}
              y1={trackY + 4}
              x2={x}
              y2={trackY + 12}
              stroke="#bfbfbf"
              strokeWidth={1}
            />
            <text
              x={x}
              y={trackY + 24}
              textAnchor="middle"
              fontSize={10}
              fill="#8c8c8c"
            >
              {m.format("MMM")}
            </text>
          </g>
        );
      })}
      {milestones.map((ms) => {
        const x = PAD + dateToFrac(ms.date) * trackW;
        return (
          <Tooltip
            key={ms.label}
            title={`${ms.label} — ${dayjs(ms.date).format("MMM D, YYYY")}`}
          >
            <g style={{ cursor: "pointer" }}>
              <polygon
                points={`${x},${trackY - 10} ${x + 7},${trackY} ${x},${trackY + 10} ${x - 7},${trackY}`}
                fill={ms.color}
              />
              <text
                x={x}
                y={trackY - 14}
                textAnchor="middle"
                fontSize={9}
                fontWeight="600"
                fill={ms.color}
              >
                {ms.label}
              </text>
            </g>
          </Tooltip>
        );
      })}
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
function CumulativeChart({ cumulativeData, cumulativeTarget }) {
  if (
    !Array.isArray(cumulativeData) ||
    !Array.isArray(cumulativeTarget) ||
    cumulativeData.length === 0 ||
    cumulativeTarget.length === 0
  ) {
    return (
      <div style={{ padding: "24px 0" }}>
        <Text type="secondary">
          No cumulative progress history yet. Add data and volume activity to
          populate this chart.
        </Text>
      </div>
    );
  }
  const W = 800;
  const H = 180;
  const PADL = 52;
  const PADR = 16;
  const PADT = 16;
  const PADB = 32;
  const chartW = W - PADL - PADR;
  const chartH = H - PADT - PADB;
  const maxVal = Math.max(...cumulativeData, ...cumulativeTarget) * 1.05;
  const weeks = cumulativeData.length;
  const toX = (i) => PADL + (i / (weeks - 1)) * chartW;
  const toY = (v) => PADT + chartH - (v / maxVal) * chartH;
  const pathD = (data) =>
    data
      .map(
        (v, i) =>
          `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)},${toY(v).toFixed(1)}`,
      )
      .join(" ");
  const areaD = (data) =>
    `${pathD(data)} L ${toX(weeks - 1).toFixed(1)},${(PADT + chartH).toFixed(1)} L ${PADL},${(PADT + chartH).toFixed(1)} Z`;
  const yTicks = [0, 10000, 20000, 30000];
  const xTicks = [0, 4, 8, 12, 16, 20, 24];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", height: H }}
      aria-label="Cumulative items proofread"
    >
      {yTicks.map((v) => (
        <g key={v}>
          <line
            x1={PADL}
            y1={toY(v)}
            x2={PADL + chartW}
            y2={toY(v)}
            stroke="#f0f0f0"
            strokeWidth={1}
          />
          <text
            x={PADL - 6}
            y={toY(v) + 4}
            textAnchor="end"
            fontSize={9}
            fill="#8c8c8c"
          >
            {v === 0 ? "0" : `${v / 1000}k`}
          </text>
        </g>
      ))}
      {xTicks.map((i) => (
        <text
          key={i}
          x={toX(i)}
          y={PADT + chartH + 16}
          textAnchor="middle"
          fontSize={9}
          fill="#8c8c8c"
        >
          Wk {i + 1}
        </text>
      ))}
      <path d={areaD(cumulativeTarget)} fill="#1890ff" opacity={0.06} />
      <path
        d={pathD(cumulativeTarget)}
        fill="none"
        stroke="#1890ff"
        strokeWidth={1.5}
        strokeDasharray="5 3"
      />
      <path d={areaD(cumulativeData)} fill="#52c41a" opacity={0.12} />
      <path
        d={pathD(cumulativeData)}
        fill="none"
        stroke="#52c41a"
        strokeWidth={2}
      />
      <g transform={`translate(${PADL + chartW - 160}, ${PADT})`}>
        <line x1={0} y1={8} x2={18} y2={8} stroke="#52c41a" strokeWidth={2} />
        <text x={22} y={12} fontSize={10} fill="#595959">
          Actual
        </text>
        <line
          x1={60}
          y1={8}
          x2={78}
          y2={8}
          stroke="#1890ff"
          strokeWidth={1.5}
          strokeDasharray="4 2"
        />
        <text x={82} y={12} fontSize={10} fill="#595959">
          Target
        </text>
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
          strokeColor={
            pct >= 80 ? "#52c41a" : pct >= 40 ? "#faad14" : "#ff4d4f"
          }
          showInfo={false}
        />
        <Text style={{ width: 34, textAlign: "right" }}>{pct}%</Text>
      </Space>
    ),
  },
  { title: "Status", dataIndex: "status", key: "status", render: statusTag },
  {
    title: "ETA",
    dataIndex: "eta",
    key: "eta",
    render: (eta) => <Text type="secondary">{eta}</Text>,
  },
];

// ─── Main Component ───────────────────────────────────────────────────────────

function AnnotationDashboard() {
  const {
    quotaData,
    allQuotaData,
    proofreaderData,
    datasets,
    milestones,
    cumulativeData,
    cumulativeTarget,
    atRisk,
    upcomingMilestones,
    globalProgress,
    isWorker,
    activeWorker,
  } = useProjectManager();

  const [filter, setFilter] = useState("all");

  // ── KPI calculations ──────────────────────────────────────────────────────
  // Weekly quota progress (uses role-filtered quotaData)
  const totalActual = useMemo(
    () =>
      quotaData.reduce(
        (sum, row) =>
          sum +
          row.actualMon +
          row.actualTue +
          row.actualWed +
          row.actualThu +
          row.actualFri +
          row.actualSat +
          row.actualSun,
        0,
      ),
    [quotaData],
  );
  const totalTarget = useMemo(
    () =>
      quotaData.reduce(
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
      ),
    [quotaData],
  );

  const totalSamplesCount = useMemo(
    () => datasets.reduce((s, d) => s + d.total, 0),
    [datasets],
  );
  const overallPct =
    totalTarget > 0 ? Math.round((totalActual / totalTarget) * 100) : 0;
  const activeDatasetsCount = datasets.filter(
    (d) => d.status === "in_progress",
  ).length;
  const activeProofreadersCount = proofreaderData.filter(
    (p) => p.status === "online" || p.status === "away",
  ).length;

  // Volume progress — admin = global 1000, worker = their 250
  const volProgress = isWorker
    ? (globalProgress?.by_worker?.[activeWorker] ?? {
        done: 0,
        total: 250,
        pct: 0,
      })
    : (globalProgress ?? { done: 0, total: 1000, pct: 0 });

  // Filtered datasets
  const filteredDatasets = useMemo(() => {
    if (filter === "all") return datasets;
    if (filter === "high") return datasets.filter((d) => d.priority === "high");
    if (filter === "blocked")
      return datasets.filter((d) => d.status === "blocked");
    return datasets;
  }, [filter, datasets]);

  const filterBtns = [
    { key: "all", label: "All" },
    { key: "high", label: "High Priority" },
    { key: "blocked", label: "Blocked" },
  ];
  const isEmptyProject =
    (globalProgress?.total ?? 0) === 0 &&
    datasets.length === 0 &&
    milestones.length === 0;

  return (
    <div style={{ padding: "0 4px" }}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Live vs seeded data"
        description="Volume progress and quota attainment are live from the Project Manager JSON. Timeline, dataset milestones, and some analytics in this view still come from seeded PM data unless your active JSON populates them."
      />

      {isEmptyProject && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Fresh project"
          description="No project data is loaded yet. Open Settings to choose a metadata JSON and storage root, then use Sync Storage in Volume Tracker to ingest your supported project volumes."
        />
      )}

      {/* ── Header ── */}
      <div style={{ marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, color: "#262626" }}>
          {isWorker ? "My Dashboard" : "Neural Dataset Proofreading – 6 Months"}
        </Title>
        <Text type="secondary" style={{ fontSize: 13 }}>
          {PROJECT_START.format("MMM D, YYYY")} →{" "}
          {PROJECT_END.format("MMM D, YYYY")} · <b>Real-time Context Sync</b>
        </Text>
      </div>

      {/* ── KPI Cards ── */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        {/* ① Volume Progress — derived from actual done status of 1000 volumes */}
        <Col span={6}>
          <Card
            size="small"
            bordered={false}
            style={{
              background: "#f9f0ff",
              borderLeft: "4px solid #722ed1",
              boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
            }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {isWorker ? "My Volumes Done" : "Global Volume Progress"}
                </Text>
              }
              value={volProgress.done}
              suffix={`/ ${volProgress.total}`}
              prefix={<DatabaseOutlined style={{ color: "#722ed1" }} />}
              valueStyle={{
                color: "#722ed1",
                fontSize: 20,
                fontWeight: "bold",
              }}
            />
            <div style={{ marginTop: 8 }}>
              <Progress
                percent={parseFloat(volProgress.pct ?? 0)}
                size="small"
                showInfo={false}
                strokeColor="#722ed1"
              />
              <Text type="secondary" style={{ fontSize: 11 }}>
                {volProgress.pct ?? 0}% of{" "}
                {isWorker ? "250 assigned" : "1,000 total"} volumes done
              </Text>
            </div>
          </Card>
        </Col>

        {/* ② Weekly Points */}
        <Col span={6}>
          <Card
            size="small"
            bordered={false}
            style={{
              background: "#f6ffed",
              borderLeft: "4px solid #52c41a",
              boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
            }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Weekly Points
                </Text>
              }
              value={totalActual.toLocaleString()}
              suffix={`/ ${totalTarget.toLocaleString()}`}
              prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
              valueStyle={{
                color: "#52c41a",
                fontSize: 20,
                fontWeight: "bold",
              }}
            />
            <div style={{ marginTop: 8 }}>
              <Progress
                percent={overallPct}
                size="small"
                showInfo={false}
                strokeColor="#52c41a"
              />
            </div>
          </Card>
        </Col>

        {/* ③ Active Datasets (admin only, for worker show accuracy) */}
        <Col span={6}>
          <Card
            size="small"
            bordered={false}
            style={{
              background: "#e6f7ff",
              borderLeft: "4px solid #1890ff",
              boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
            }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Active Datasets
                </Text>
              }
              value={activeDatasetsCount}
              suffix={`/ ${datasets.length}`}
              prefix={<FileTextOutlined style={{ color: "#1890ff" }} />}
              valueStyle={{
                color: "#1890ff",
                fontSize: 20,
                fontWeight: "bold",
              }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {totalSamplesCount.toLocaleString()} total samples
            </Text>
          </Card>
        </Col>

        {/* ④ Team status */}
        <Col span={6}>
          <Card
            size="small"
            bordered={false}
            style={{
              background: "#fff7e6",
              borderLeft: "4px solid #fa8c16",
              boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
            }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {isWorker ? "My Weekly Points" : "Proofreaders Online"}
                </Text>
              }
              value={isWorker ? totalActual : activeProofreadersCount}
              suffix={isWorker ? undefined : `/ ${allQuotaData.length}`}
              prefix={
                isWorker ? (
                  <RiseOutlined style={{ color: "#fa8c16" }} />
                ) : (
                  <TeamOutlined style={{ color: "#fa8c16" }} />
                )
              }
              valueStyle={{
                color: "#fa8c16",
                fontSize: 20,
                fontWeight: "bold",
              }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {isWorker ? "Points this week" : "Team-wide active status"}
            </Text>
          </Card>
        </Col>
      </Row>

      {/* ── Timeline ── */}
      <Card
        size="small"
        title={<Text strong>6-Month Project Timeline</Text>}
        style={{ marginBottom: 20, borderRadius: 8 }}
        bodyStyle={{ paddingTop: 8 }}
      >
        <SixMonthTimeline milestones={milestones} />
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
            style={{ marginBottom: 20, borderRadius: 8 }}
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
                <Text strong>Weekly Progress</Text>
              </Space>
            }
            style={{ marginBottom: 12, borderRadius: 8 }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              Total items annotated vs. target
            </Text>
            <div style={{ marginTop: 10 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 4,
                }}
              >
                <Text style={{ fontSize: 12 }}>Completed</Text>
                <Text strong style={{ fontSize: 12 }}>
                  {totalActual.toLocaleString()}
                </Text>
              </div>
              <Progress
                percent={overallPct}
                strokeColor="#1890ff"
                size="small"
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 4,
                }}
              >
                <Text type="secondary" style={{ fontSize: 11 }}>
                  Target: {totalTarget.toLocaleString()}
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {overallPct}%
                </Text>
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
            style={{ marginBottom: 12, borderRadius: 8 }}
          >
            {atRisk.map((item, idx) => (
              <div key={idx}>
                {idx > 0 && <Divider style={{ margin: "6px 0" }} />}
                <div
                  style={{ display: "flex", alignItems: "flex-start", gap: 8 }}
                >
                  {item.icon === "clock" ? (
                    <ClockCircleOutlined
                      style={{ color: "#faad14", marginTop: 2 }}
                    />
                  ) : item.icon === "blocked" ? (
                    <StopOutlined style={{ color: "#ff4d4f", marginTop: 2 }} />
                  ) : (
                    <MinusCircleOutlined
                      style={{ color: "#faad14", marginTop: 2 }}
                    />
                  )}
                  <div>
                    <Text strong style={{ fontSize: 12 }}>
                      {item.label}
                    </Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {item.reason}
                    </Text>
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
            style={{ borderRadius: 8 }}
          >
            {upcomingMilestones.map((ms, idx) => (
              <div key={idx}>
                {idx > 0 && <Divider style={{ margin: "6px 0" }} />}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <Text style={{ fontSize: 12 }}>{ms.label}</Text>
                  <Tag color="cyan" style={{ fontSize: 10, margin: 0 }}>
                    {ms.date}
                  </Tag>
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
        style={{ marginBottom: 8, borderRadius: 8 }}
        bodyStyle={{ paddingTop: 8 }}
      >
        <CumulativeChart
          cumulativeData={cumulativeData}
          cumulativeTarget={cumulativeTarget}
        />
      </Card>
    </div>
  );
}

export default AnnotationDashboard;
