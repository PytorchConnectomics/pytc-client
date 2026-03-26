import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Card,
  Table,
  Tag,
  Select,
  Button,
  Progress,
  Typography,
  Row,
  Col,
  Statistic,
  Tooltip,
  Space,
  Badge,
  Popconfirm,
} from "antd";
import {
  DatabaseOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  FilterOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useProjectManager } from "../../contexts/ProjectManagerContext";

const { Title, Text } = Typography;

// ── Status helpers ────────────────────────────────────────────────────────────
const STATUS_CONFIG = {
  todo: { label: "To Do", color: "default", badgeColor: "#d9d9d9" },
  in_progress: {
    label: "In Progress",
    color: "processing",
    badgeColor: "#1890ff",
  },
  done: { label: "Done", color: "success", badgeColor: "#52c41a" },
};

const STATUS_OPTIONS = Object.entries(STATUS_CONFIG).map(
  ([value, { label }]) => ({ value, label }),
);
const ALL_STATUSES = [{ value: "", label: "All statuses" }, ...STATUS_OPTIONS];

// ── Workers list (mirrors backend) ────────────────────────────────────────────
const WORKER_OPTIONS_ALL = [
  { value: "", label: "All workers" },
  { value: "alex", label: "Alex Rivera" },
  { value: "jordan", label: "Jordan Smith" },
  { value: "taylor", label: "Sam Taylor" },
  { value: "morgan", label: "Morgan Lee" },
];

// ── Main Component ─────────────────────────────────────────────────────────────
function VolumeTracker() {
  const {
    isAdmin,
    isWorker,
    activeWorker,
    globalProgress,
    updateVolumeStatus,
  } = useProjectManager();

  const [volumes, setVolumes] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loadingVols, setLoadingVols] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [workerFilter, setWorkerFilter] = useState(
    isWorker ? activeWorker : "",
  );
  const [updatingId, setUpdatingId] = useState(null);

  // When role/activeWorker changes, reset worker filter
  useEffect(() => {
    setWorkerFilter(isWorker ? activeWorker : "");
    setPage(1);
  }, [isWorker, activeWorker]);

  // ── Fetch volumes ─────────────────────────────────────────────────────────
  const fetchVolumes = useCallback(async () => {
    setLoadingVols(true);
    try {
      const params = { page, page_size: pageSize };
      if (workerFilter) params.assignee = workerFilter;
      if (statusFilter) params.status = statusFilter;
      const res = await fetch(
        `http://localhost:4242/api/pm/volumes?${new URLSearchParams(params)}`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setVolumes(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      console.error("[VolumeTracker] fetch failed:", err);
    } finally {
      setLoadingVols(false);
    }
  }, [page, pageSize, workerFilter, statusFilter]);

  useEffect(() => {
    fetchVolumes();
  }, [fetchVolumes]);

  // ── Status update handler ─────────────────────────────────────────────────
  const handleStatusChange = async (volumeId, newStatus) => {
    setUpdatingId(volumeId);
    try {
      await updateVolumeStatus(volumeId, newStatus);
      setVolumes((prev) =>
        prev.map((v) => (v.id === volumeId ? { ...v, status: newStatus } : v)),
      );
    } finally {
      setUpdatingId(null);
    }
  };

  // ── Stats from globalProgress for this view ───────────────────────────────
  const workerProgress = useMemo(() => {
    if (isWorker && globalProgress?.by_worker) {
      return globalProgress.by_worker[activeWorker] ?? null;
    }
    return null;
  }, [isAdmin, isWorker, activeWorker, globalProgress]);

  const displayPct =
    isWorker && workerProgress
      ? workerProgress.pct
      : (globalProgress?.pct ?? 0);
  const displayDone =
    isWorker && workerProgress
      ? workerProgress.done
      : (globalProgress?.done ?? 0);
  const displayTotal =
    isWorker && workerProgress
      ? workerProgress.total
      : (globalProgress?.total ?? 1000);
  const displayIP =
    isWorker && workerProgress
      ? workerProgress.in_progress
      : (globalProgress?.in_progress ?? 0);

  // ── Columns ───────────────────────────────────────────────────────────────
  const columns = [
    {
      title: "Volume ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      render: (id) => (
        <Text strong style={{ fontFamily: "monospace", fontSize: 12 }}>
          {id}
        </Text>
      ),
    },
    // Admin-only: assignee column
    ...(isAdmin
      ? [
          {
            title: "Assignee",
            dataIndex: "assignee",
            key: "assignee",
            width: 130,
            render: (key) => {
              const opt = WORKER_OPTIONS_ALL.find((w) => w.value === key);
              return (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {opt?.label ?? key}
                </Text>
              );
            },
          },
        ]
      : []),
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 160,
      render: (status, record) => {
        const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.todo;
        return (
          <Select
            size="small"
            value={status}
            loading={updatingId === record.id}
            disabled={updatingId === record.id}
            onChange={(val) => handleStatusChange(record.id, val)}
            style={{ width: 140 }}
            options={STATUS_OPTIONS.map(({ value, label }) => ({
              value,
              label: (
                <Space size={4}>
                  <Badge color={STATUS_CONFIG[value].badgeColor} />
                  {label}
                </Space>
              ),
            }))}
          />
        );
      },
    },
  ];

  return (
    <div style={{ padding: "0 4px" }}>
      {/* ── Header ── */}
      <div style={{ marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>
          <DatabaseOutlined style={{ marginRight: 8 }} />
          {isWorker ? "My Volumes" : "Volume Tracker"}
        </Title>
        <Text type="secondary">
          {isWorker
            ? `Showing your 250 assigned volumes · click status to update`
            : `All 1,000 volumes · click status to update`}
        </Text>
      </div>

      {/* ── KPI Strip ── */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={6}>
          <Card
            size="small"
            style={{ background: "#f6ffed", borderLeft: "4px solid #52c41a" }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 11 }}>
                  Done
                </Text>
              }
              value={displayDone}
              suffix={`/ ${displayTotal}`}
              prefix={<CheckCircleOutlined style={{ color: "#52c41a" }} />}
              valueStyle={{
                color: "#52c41a",
                fontSize: 18,
                fontWeight: "bold",
              }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card
            size="small"
            style={{ background: "#e6f7ff", borderLeft: "4px solid #1890ff" }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 11 }}>
                  In Progress
                </Text>
              }
              value={displayIP}
              prefix={
                <SyncOutlined
                  style={{ color: "#1890ff" }}
                  spin={displayIP > 0}
                />
              }
              valueStyle={{
                color: "#1890ff",
                fontSize: 18,
                fontWeight: "bold",
              }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card
            size="small"
            style={{ background: "#fff7e6", borderLeft: "4px solid #fa8c16" }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 11 }}>
                  To Do
                </Text>
              }
              value={displayTotal - displayDone - displayIP}
              prefix={<ClockCircleOutlined style={{ color: "#fa8c16" }} />}
              valueStyle={{
                color: "#fa8c16",
                fontSize: 18,
                fontWeight: "bold",
              }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ borderLeft: "4px solid #722ed1" }}>
            <Text
              type="secondary"
              style={{ fontSize: 11, display: "block", marginBottom: 4 }}
            >
              {isWorker ? "My Progress" : "Global Progress"}
            </Text>
            <Progress
              percent={parseFloat(displayPct)}
              size="small"
              strokeColor="#722ed1"
              format={(p) => (
                <Text style={{ fontSize: 12, fontWeight: "bold" }}>{p}%</Text>
              )}
            />
          </Card>
        </Col>
      </Row>

      {/* ── Table with Filters ── */}
      <Card
        size="small"
        title={
          <Space>
            <FilterOutlined />
            <Text strong>Volume List</Text>
            <Tag>{total.toLocaleString()} matching</Tag>
          </Space>
        }
        extra={
          <Space>
            {/* Assignee filter — admin only */}
            {isAdmin && (
              <Select
                size="small"
                style={{ width: 140 }}
                value={workerFilter}
                onChange={(v) => {
                  setWorkerFilter(v);
                  setPage(1);
                }}
                options={WORKER_OPTIONS_ALL}
              />
            )}
            <Select
              size="small"
              style={{ width: 140 }}
              value={statusFilter}
              onChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
              options={ALL_STATUSES}
            />
            <Tooltip title="Refresh">
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={fetchVolumes}
                loading={loadingVols}
              />
            </Tooltip>
          </Space>
        }
      >
        <Table
          dataSource={volumes}
          columns={columns}
          loading={loadingVols}
          rowKey="id"
          size="small"
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (t, [s, e]) => `${s}–${e} of ${t}`,
            onChange: (p) => setPage(p),
          }}
          scroll={{ x: isAdmin ? 480 : 360, y: "calc(100vh - 440px)" }}
        />
      </Card>
    </div>
  );
}

export default VolumeTracker;
