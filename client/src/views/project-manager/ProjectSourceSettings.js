import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Input,
  Popconfirm,
  Space,
  Table,
  Typography,
  message,
} from "antd";
import {
  CopyOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { getPMSchema } from "../../api";
import UnifiedFileInput from "../../components/UnifiedFileInput";
import { useProjectManager } from "../../contexts/ProjectManagerContext";

const { Paragraph, Text, Title } = Typography;

const schemaColumns = [
  {
    title: "Field",
    dataIndex: "field",
    key: "field",
    width: 180,
    render: (value) => <Text code>{value}</Text>,
  },
  {
    title: "Level",
    dataIndex: "level",
    key: "level",
    width: 130,
    render: (value) => (
      <span
        style={{
          display: "inline-flex",
          padding: "5px 9px",
          borderRadius: 999,
          background:
            value === "required"
              ? "rgba(176, 49, 47, 0.10)"
              : value === "recommended"
                ? "rgba(20, 108, 99, 0.10)"
                : "rgba(98, 81, 48, 0.08)",
          color:
            value === "required"
              ? "#b0312f"
              : value === "recommended"
                ? "#146c63"
                : "#7c6f59",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.04em",
        }}
      >
        {(value || "optional").toUpperCase()}
      </span>
    ),
  },
  {
    title: "Type",
    dataIndex: "type",
    key: "type",
    width: 140,
    render: (value) => <Text code>{value}</Text>,
  },
  {
    title: "Purpose",
    dataIndex: "description",
    key: "description",
  },
];

function SchemaTable({ rows }) {
  return (
    <Table
      size="small"
      columns={schemaColumns}
      dataSource={(rows || []).map((row) => ({ ...row, key: row.field }))}
      pagination={false}
    />
  );
}

function StatusBadge({ ok, goodLabel, badLabel }) {
  return (
    <span
      style={{
        display: "inline-flex",
        padding: "4px 10px",
        borderRadius: 999,
        background: ok ? "rgba(82, 196, 26, 0.12)" : "rgba(98, 81, 48, 0.08)",
        color: ok ? "#52a21a" : "#7c6f59",
        fontSize: 11,
        fontWeight: 700,
      }}
    >
      {ok ? goodLabel : badLabel}
    </span>
  );
}

function ProjectSourceSettings({ onOpenVolumes, isModal = false }) {
  const {
    pmConfig,
    projectInfo,
    isAdmin,
    loading,
    configLoading,
    globalProgress,
    resetData,
    updateProjectConfig,
    refreshPmState,
    ingestData,
  } = useProjectManager();
  const [metadataPath, setMetadataPath] = useState("");
  const [dataRoot, setDataRoot] = useState("");
  const [schemaData, setSchemaData] = useState(null);
  const [schemaLoading, setSchemaLoading] = useState(true);

  useEffect(() => {
    setMetadataPath(pmConfig?.metadata_path ?? "");
    setDataRoot(pmConfig?.data_root ?? "");
  }, [pmConfig?.data_root, pmConfig?.metadata_path]);

  useEffect(() => {
    let cancelled = false;

    const loadSchema = async () => {
      setSchemaLoading(true);
      try {
        const nextSchema = await getPMSchema();
        if (!cancelled) {
          setSchemaData(nextSchema);
        }
      } catch (error) {
        if (!cancelled) {
          message.error("Failed to load Project Manager schema reference.");
        }
      } finally {
        if (!cancelled) {
          setSchemaLoading(false);
        }
      }
    };

    loadSchema();
    return () => {
      cancelled = true;
    };
  }, []);

  const trackedVolumes = globalProgress?.total ?? 0;
  const needsInitialProject = !pmConfig?.metadata_exists || trackedVolumes === 0;
  const hasUnsavedChanges =
    metadataPath !== (pmConfig?.metadata_path ?? "") ||
    dataRoot !== (pmConfig?.data_root ?? "");

  const setupState = useMemo(() => {
    if (!pmConfig?.metadata_exists) {
      return {
        title: "Pick the metadata JSON",
        description:
          "Choose the JSON file this project manager should own, then save the path.",
      };
    }
    if (!pmConfig?.data_root_exists || !pmConfig?.data_root_is_dir) {
      return {
        title: "Connect the storage root",
        description:
          "Set a valid directory containing your supported volume files or dataset directories, then save again.",
      };
    }
    if (trackedVolumes === 0) {
      return {
        title: "Sync storage",
        description:
          "Scan the storage root to populate the volumes array in the active JSON.",
      };
    }
    return {
      title: "Track work",
      description:
        "Open Volume Tracker to assign owners and update status as the project moves.",
    };
  }, [
    pmConfig?.data_root_exists,
    pmConfig?.data_root_is_dir,
    pmConfig?.metadata_exists,
    trackedVolumes,
  ]);

  const starterJson = useMemo(
    () => JSON.stringify(schemaData?.blank_template ?? {}, null, 2),
    [schemaData?.blank_template],
  );

  const skillCommand = useMemo(
    () =>
      '/generate-project-manager-json "/absolute/path/to/data/root" "/absolute/path/to/project_manager_data.json"',
    [],
  );

  const handleSave = async () => {
    await updateProjectConfig({
      metadata_path: metadataPath,
      data_root: dataRoot,
    });
  };

  const handleLoadExistingJson = async () => {
    if (!metadataPath) {
      message.error("Choose a project JSON file first.");
      return;
    }
    await updateProjectConfig({ metadata_path: metadataPath });
  };

  const handleResetPaths = async () => {
    await updateProjectConfig({
      metadata_path: "",
      data_root: "",
    });
  };

  const handleCopy = async (label, value) => {
    try {
      await navigator.clipboard.writeText(value);
      message.success(`${label} copied to clipboard.`);
    } catch (error) {
      message.error(`Failed to copy ${label.toLowerCase()}.`);
    }
  };

  const projectLabel = projectInfo?.name || pmConfig?.project_name || "Project";
  const canSync =
    !hasUnsavedChanges &&
    !!pmConfig?.metadata_exists &&
    !!pmConfig?.data_root_exists &&
    !!pmConfig?.data_root_is_dir;

  return (
    <div style={{ padding: "0 4px" }}>
      {!isModal && (
        <div style={{ marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>
            {isAdmin ? "Project Setup" : "Project Info"}
          </Title>
          <Text type="secondary">
            Keep the core flow simple: choose the JSON, connect storage, sync
            volumes, then move into tracking.
          </Text>
        </div>
      )}

      <Card
        size="small"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={refreshPmState}
              loading={loading || configLoading}
            >
              Refresh
            </Button>
            {isAdmin && (
              <Button
                type="primary"
                icon={<SyncOutlined />}
                onClick={ingestData}
                loading={loading}
                disabled={!canSync}
              >
                Sync Storage
              </Button>
            )}
          </Space>
        }
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {isAdmin && needsInitialProject && (
            <Alert
              type="info"
              showIcon
              message="Start by loading a project JSON or creating a fresh one."
              description="You can drag a JSON file onto the field below, browse for one, or start a blank project and sync storage afterward."
            />
          )}

          <div>
            <Text strong style={{ display: "block", marginBottom: 4 }}>
              {setupState.title}
            </Text>
            <Text type="secondary">{setupState.description}</Text>
          </div>

          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="Project">{projectLabel}</Descriptions.Item>
            <Descriptions.Item label="Tracked Volumes">
              {trackedVolumes}
            </Descriptions.Item>
            <Descriptions.Item label="Metadata JSON" span={2}>
              <Space wrap>
                <Text code>{pmConfig?.metadata_path || "Not configured"}</Text>
                <StatusBadge
                  ok={pmConfig?.metadata_exists}
                  goodLabel="Found"
                  badLabel="Missing"
                />
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Storage Root" span={2}>
              <Space wrap>
                <Text code>{pmConfig?.data_root || "Not configured"}</Text>
                <StatusBadge
                  ok={pmConfig?.data_root_exists && pmConfig?.data_root_is_dir}
                  goodLabel="Ready"
                  badLabel="Missing"
                />
              </Space>
            </Descriptions.Item>
          </Descriptions>

          <div>
            <Text strong style={{ display: "block", marginBottom: 6 }}>
              1. Metadata JSON path
            </Text>
            <UnifiedFileInput
              value={metadataPath}
              onChange={(value) =>
                setMetadataPath(
                  typeof value === "string" ? value : value?.path || "",
                )
              }
              disabled={!isAdmin || configLoading}
              placeholder="/absolute/path/to/project_manager_data.json"
              selectionType="file"
              style={{ marginBottom: 8 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Use an existing file or a new file path whose parent directory
              already exists.
            </Text>
            {isAdmin && (
              <Space wrap style={{ marginTop: 8 }}>
                <Button
                  icon={<FolderOpenOutlined />}
                  onClick={handleLoadExistingJson}
                  disabled={!metadataPath}
                  loading={configLoading}
                >
                  Load Existing JSON
                </Button>
                <Popconfirm
                  title="Start a fresh project?"
                  description="This clears the active metadata file back to a blank starter state."
                  onConfirm={resetData}
                  okText="Start Fresh"
                  cancelText="Cancel"
                  okButtonProps={{ danger: true }}
                >
                  <Button danger loading={loading}>
                    Start Fresh Project
                  </Button>
                </Popconfirm>
              </Space>
            )}
          </div>

          <div>
            <Text strong style={{ display: "block", marginBottom: 6 }}>
              2. Storage root
            </Text>
            <UnifiedFileInput
              value={dataRoot}
              onChange={(value) =>
                setDataRoot(typeof value === "string" ? value : value?.path || "")
              }
              disabled={!isAdmin || configLoading}
              placeholder="/absolute/path/to/data/root"
              selectionType="directory"
              style={{ marginBottom: 8 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Sync scans this directory recursively for supported volume files,
              dataset containers, and image-stack directories, then updates the
              active JSON.
            </Text>
          </div>

          {isAdmin && (
            <Space wrap>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                disabled={!hasUnsavedChanges}
                loading={configLoading}
              >
                Save Setup
              </Button>
              <Button
                icon={<FolderOpenOutlined />}
                onClick={handleResetPaths}
                disabled={!hasUnsavedChanges}
                loading={configLoading}
              >
                Revert to Defaults
              </Button>
              <Button onClick={onOpenVolumes} disabled={trackedVolumes === 0}>
                Open Volume Tracker
              </Button>
            </Space>
          )}
        </Space>
      </Card>

      <Card size="small" title="Optional Resources">
        <Collapse
          items={[
            {
              key: "schema",
              label: "Schema reference",
              children: schemaLoading ? (
                <Text type="secondary">Loading schema reference…</Text>
              ) : (
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <Text type="secondary">
                    The minimum useful project file has `project_info`,
                    `workers`, `users`, and `volumes`.
                  </Text>
                  <Text type="secondary">
                    Supported inputs:{" "}
                    {(schemaData?.supported_volume_inputs || []).join(", ")}
                  </Text>
                  <Collapse
                    size="small"
                    items={[
                      {
                        key: "top-level",
                        label: "Top-level fields",
                        children: (
                          <SchemaTable rows={schemaData?.top_level_fields} />
                        ),
                      },
                      {
                        key: "volumes",
                        label: "Volume rows",
                        children: <SchemaTable rows={schemaData?.volume_fields} />,
                      },
                      {
                        key: "workers",
                        label: "Worker rows",
                        children: <SchemaTable rows={schemaData?.worker_fields} />,
                      },
                      {
                        key: "users",
                        label: "User rows",
                        children: <SchemaTable rows={schemaData?.user_fields} />,
                      },
                    ]}
                  />
                </Space>
              ),
            },
            {
              key: "starter-json",
              label: "Starter JSON template",
              extra: (
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={(event) => {
                    event.stopPropagation();
                    handleCopy("Starter JSON", starterJson);
                  }}
                  disabled={!schemaData}
                >
                  Copy
                </Button>
              ),
              children: (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <Text type="secondary">
                    Save this starter file anywhere, then point the app at it.
                  </Text>
                  <Input.TextArea
                    readOnly
                    value={starterJson}
                    autoSize={{ minRows: 12, maxRows: 20 }}
                    style={{ fontFamily: "SFMono-Regular, Consolas, monospace" }}
                  />
                </Space>
              ),
            },
            {
              key: "skill",
              label: "Generate with Claude Code",
              extra: (
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={(event) => {
                    event.stopPropagation();
                    handleCopy("Claude Code command", skillCommand);
                  }}
                >
                  Copy
                </Button>
              ),
              children: (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <Paragraph style={{ marginBottom: 0 }}>
                    The repo-local skill scans a directory of supported volume
                    inputs and generates a compatible project JSON.
                  </Paragraph>
                  <Input.TextArea
                    readOnly
                    value={skillCommand}
                    autoSize={{ minRows: 4, maxRows: 6 }}
                    style={{ fontFamily: "SFMono-Regular, Consolas, monospace" }}
                  />
                  <Space size={8}>
                    <RobotOutlined />
                    <Text type="secondary">
                      `.claude/skills/generate-project-manager-json/`
                    </Text>
                  </Space>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

export default ProjectSourceSettings;
