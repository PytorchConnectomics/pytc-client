import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Alert,
  Card,
  Empty,
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

// ── Main Component ─────────────────────────────────────────────────────────────
function VolumeTracker({ onOpenSettings }) {
  const {
    isAdmin,
    isWorker,
    activeWorker,
    workers,
    globalProgress,
    pmConfig,
    getVolumes,
    updateVolumeStatus,
    updateVolumeAssignee,
    ingestData,
    loading: pmLoading,
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
  const workerOptions = useMemo(
    () => [
      { value: "", label: "Unassigned" },
      ...(workers || []).map((worker) => ({
        value: worker.key,
        label: worker.name,
      })),
    ],
    [workers],
  );
  const workerFilterOptions = useMemo(
    () => [
      { value: "", label: "All workers" },
      ...(workers || []).map((worker) => ({
        value: worker.key,
        label: worker.name,
      })),
    ],
    [workers],
  );

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

      const data = await getVolumes(params);
      setVolumes(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      console.error("[VolumeTracker] fetch failed:", err);
    } finally {
      setLoadingVols(false);
    }
  }, [page, pageSize, workerFilter, statusFilter, getVolumes]);

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

  const handleAssigneeChange = async (volumeId, nextAssignee) => {
    const assignee = nextAssignee || null;
    setUpdatingId(volumeId);
    try {
      await updateVolumeAssignee(volumeId, assignee);
      setVolumes((prev) =>
        prev.map((v) => (v.id === volumeId ? { ...v, assignee } : v)),
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
  }, [isWorker, activeWorker, globalProgress]);

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

  const emptyState = useMemo(() => {
    if (!pmConfig?.metadata_exists) {
      return {
        title: "Project settings are not configured yet.",
        description:
          "Open Settings to choose the metadata JSON that this module should read and write.",
      };
    }
    if (!pmConfig?.data_root_exists || !pmConfig?.data_root_is_dir) {
      return {
        title: "Storage root is not configured.",
        description:
          "Open Settings and choose a valid directory that contains your supported volume files or dataset directories.",
      };
    }
    return {
      title: "No tracked volumes yet.",
      description:
        "Run Sync with Storage to scan the configured root and populate the tracker.",
    };
  }, [
    pmConfig?.data_root_exists,
    pmConfig?.data_root_is_dir,
    pmConfig?.metadata_exists,
  ]);

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
            width: 180,
            render: (key, record) => {
              return (
                <Select
                  size="small"
                  value={key ?? ""}
                  loading={updatingId === record.id}
                  disabled={updatingId === record.id}
                  onChange={(value) => handleAssigneeChange(record.id, value)}
                  style={{ width: 160 }}
                  options={workerOptions}
                />
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
            ? `Showing your ${displayTotal} assigned volumes · update status as you work`
            : `All ${globalProgress?.total ?? total} tracked volumes · assign owners and update status here`}
        </Text>
      </div>

      {/* ── KPI Strip ── */}
      {total === 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={emptyState.title}
          description={
            <Space wrap>
              <Text type="secondary">{emptyState.description}</Text>
              {isAdmin && onOpenSettings && (
                <Button size="small" onClick={onOpenSettings}>
                  Open Settings
                </Button>
              )}
            </Space>
          }
        />
      )}

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
            {/* Sync button — admin only */}
            {isAdmin && (
              <Popconfirm
                title="Refresh volume list?"
                description="This will scan the physical storage for newly discovered supported project volumes."
                onConfirm={async () => {
                  await ingestData();
                  fetchVolumes();
                }}
                okText="Scan"
                cancelText="Cancel"
              >
                <Button
                  size="small"
                  type="primary"
                  icon={<SyncOutlined />}
                  loading={pmLoading}
                >
                  Sync with Storage
                </Button>
              </Popconfirm>
            )}

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
                options={workerFilterOptions}
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
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={emptyState.description}
              >
                <Space wrap>
                  {isAdmin && onOpenSettings && (
                    <Button size="small" onClick={onOpenSettings}>
                      Open Settings
                    </Button>
                  )}
                  {isAdmin && canShowSyncAction(pmConfig) && (
                    <Popconfirm
                      title="Refresh volume list?"
                      description="This will scan the physical storage for newly discovered supported project volumes."
                      onConfirm={async () => {
                        await ingestData();
                        fetchVolumes();
                      }}
                      okText="Scan"
                      cancelText="Cancel"
                    >
                      <Button size="small" type="primary" icon={<SyncOutlined />}>
                        Sync with Storage
                      </Button>
                    </Popconfirm>
                  )}
                </Space>
              </Empty>
            ),
          }}
          scroll={{ x: isAdmin ? 480 : 360, y: "calc(100vh - 440px)" }}
        />
      </Card>
    </div>
  );
}

function canShowSyncAction(pmConfig) {
  return !!pmConfig?.metadata_exists && !!pmConfig?.data_root_exists && !!pmConfig?.data_root_is_dir;
}

export default VolumeTracker;
