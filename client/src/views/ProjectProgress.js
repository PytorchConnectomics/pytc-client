import React, { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Empty,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useWorkflow } from "../contexts/WorkflowContext";
import { logClientEvent } from "../logging/appEventLog";

const { Text, Title } = Typography;

const STATUS_OPTIONS = [
  { value: "ground_truth", label: "Fully good" },
  { value: "needs_proofreading", label: "Needs proofreading" },
  { value: "missing_segmentation", label: "No segmentation" },
  { value: "ignored", label: "Ignored" },
];

const STATUS_META = {
  ground_truth: { color: "green", icon: <CheckCircleOutlined /> },
  needs_proofreading: { color: "gold", icon: <ClockCircleOutlined /> },
  missing_segmentation: { color: "red", icon: <WarningOutlined /> },
  ignored: { color: "default", icon: <DatabaseOutlined /> },
};

const METRIC_TONE_COLORS = {
  default: "#111827",
  good: "#047857",
  warn: "#b45309",
  bad: "#b91c1c",
};

function shortPath(path) {
  if (!path) return "Not found";
  const parts = String(path).split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 3) return parts.join("/");
  return parts.slice(-3).join("/");
}

function statusTag(status, label) {
  const meta = STATUS_META[status] || STATUS_META.ignored;
  return (
    <Tag color={meta.color} icon={meta.icon} style={{ margin: 0 }}>
      {label || status}
    </Tag>
  );
}

function MetricCard({ title, value, detail, tone = "default" }) {
  const color = METRIC_TONE_COLORS[tone] || METRIC_TONE_COLORS.default;
  return (
    <Card size="small" styles={{ body: { padding: 14 } }}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {title}
      </Text>
      <div style={{ color, fontSize: 28, fontWeight: 700, lineHeight: 1.15 }}>
        {value}
      </div>
      {detail && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {detail}
        </Text>
      )}
    </Card>
  );
}

function ProjectProgress() {
  const workflowContext = useWorkflow();
  const {
    workflow,
    projectProgress,
    refreshProjectProgress,
    updateProjectProgressVolume,
  } = workflowContext || {};
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("all");

  const loadProgress = async ({ source = "project_progress_view" } = {}) => {
    if (!workflow?.id || !refreshProjectProgress) return null;
    setLoading(true);
    try {
      const progress = await refreshProjectProgress();
      logClientEvent("project_progress_refreshed", {
        source,
        message: "Project progress view refreshed",
        data: {
          workflowId: workflow.id,
          total: progress?.summary?.total || 0,
        },
      });
      return progress;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProgress({ source: "project_progress_mount" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow?.id]);

  const summary = projectProgress?.summary || {};
  const filteredVolumes = useMemo(() => {
    const volumes = projectProgress?.volumes || [];
    if (filter === "all") return volumes;
    return volumes.filter((volume) => volume.status === filter);
  }, [filter, projectProgress?.volumes]);

  const handleStatusChange = async (volumeId, status) => {
    if (!workflow?.id || !updateProjectProgressVolume) return;
    setLoading(true);
    try {
      await updateProjectProgressVolume({ volume_id: volumeId, status });
      logClientEvent("project_progress_volume_status_changed", {
        source: "project_progress_view",
        message: "Project progress volume status changed",
        data: { workflowId: workflow.id, volumeId, status },
      });
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: "Volume",
      dataIndex: "name",
      key: "name",
      render: (_, volume) => (
        <Space direction="vertical" size={0}>
          <Text strong>{volume.name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {shortPath(volume.image_path)}
          </Text>
        </Space>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 210,
      render: (_, volume) => (
        <Space direction="vertical" size={6}>
          {statusTag(volume.status, volume.status_label)}
          <Select
            size="small"
            value={volume.status}
            options={STATUS_OPTIONS}
            style={{ width: 170 }}
            onChange={(status) => handleStatusChange(volume.id, status)}
          />
        </Space>
      ),
    },
    {
      title: "Segmentation",
      dataIndex: "segmentation_path",
      key: "segmentation_path",
      render: (_, volume) => (
        <Space direction="vertical" size={0}>
          <Text>{shortPath(volume.segmentation_path)}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {volume.segmentation_kind || "none"}
            {volume.status_source ? ` · ${volume.status_source}` : ""}
          </Text>
        </Space>
      ),
    },
    {
      title: "Set",
      dataIndex: "volume_set_name",
      key: "volume_set_name",
      width: 180,
      render: (value) => value || "Current workflow",
    },
  ];

  if (!workflow?.id) {
    return <Empty description="Start or mount a workflow to track progress." />;
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", paddingBottom: 24 }}>
      <div
        style={{
          alignItems: "flex-start",
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <Space direction="vertical" size={4}>
          <Title level={3} style={{ margin: 0 }}>
            Project Progress
          </Title>
          <Text type="secondary">
            Volume-level readout for ground truth, unproofread segmentations, and missing segmentations.
          </Text>
        </Space>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => loadProgress()}
          loading={loading}
        >
          Refresh
        </Button>
      </div>

      <div
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          marginBottom: 16,
        }}
      >
        <MetricCard
          title="Tracked volumes"
          value={summary.tracked_total ?? summary.total ?? 0}
          detail={`${summary.completion_pct ?? 0}% fully good`}
        />
        <MetricCard
          title="Fully good"
          value={summary.ground_truth ?? 0}
          detail="proofread ground truth"
          tone="good"
        />
        <MetricCard
          title="Needs proofreading"
          value={summary.needs_proofreading ?? 0}
          detail="segmentation exists"
          tone="warn"
        />
        <MetricCard
          title="No segmentation"
          value={summary.missing_segmentation ?? 0}
          detail="image only"
          tone="bad"
        />
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Space align="center" style={{ width: "100%", justifyContent: "space-between" }}>
            <Text strong>Completion</Text>
            <Text type="secondary">
              {summary.remaining ?? 0} remaining
            </Text>
          </Space>
          <Progress
            percent={summary.completion_pct || 0}
            success={{ percent: summary.completion_pct || 0 }}
          />
          <Text type="secondary">
            Segmentation coverage: {summary.segmentation_coverage_pct || 0}% have some mask or segmentation.
          </Text>
        </Space>
      </Card>

      <Space wrap style={{ marginBottom: 12 }}>
        <Select
          value={filter}
          style={{ width: 220 }}
          onChange={setFilter}
          options={[
            { value: "all", label: "All volumes" },
            ...STATUS_OPTIONS,
          ]}
        />
        {STATUS_OPTIONS.map((option) => (
          <Tag
            key={option.value}
            color={STATUS_META[option.value]?.color || "default"}
            title={projectProgress?.status_definitions?.[option.value]}
          >
            {option.label}
          </Tag>
        ))}
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={filteredVolumes}
        pagination={{ pageSize: 25, hideOnSinglePage: true }}
        locale={{ emptyText: "No tracked volumes found yet." }}
      />
    </div>
  );
}

export default ProjectProgress;
