import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Card,
  Layout,
  Menu,
  Modal,
  Typography,
  ConfigProvider,
  Space,
  Button,
  Tag,
} from "antd";
import {
  DashboardOutlined,
  TeamOutlined,
  ScheduleOutlined,
  LineChartOutlined,
  BugOutlined,
  SettingOutlined,
  DatabaseOutlined,
  SyncOutlined,
} from "@ant-design/icons";

import AnnotationDashboard from "./AnnotationDashboard";
import ProofreaderProgress from "./ProofreaderProgress";
import QuotaManagement from "./QuotaManagement";
import ModelQualityDashboard from "./ModelQualityDashboard";
import VolumeTracker from "./VolumeTracker";
import ProjectManagerLogin from "./ProjectManagerLogin";
import ProjectSourceSettings from "./ProjectSourceSettings";
import {
  ProjectManagerProvider,
  useProjectManager,
} from "../../contexts/ProjectManagerContext";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

const ProjectManagerInner = () => {
  const {
    isAuthenticated,
    user,
    logout,
    isAdmin,
    isWorker,
    pmConfig,
    projectInfo,
    globalProgress,
    ingestData,
    loading,
  } = useProjectManager();

  const [selectedKey, setSelectedKey] = useState("volumes");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const didAutoRouteRef = useRef(false);
  const didAutoOpenSetupRef = useRef(false);

  const trackedVolumes = globalProgress?.total ?? 0;
  const needsJson = !pmConfig?.metadata_exists;
  const needsSync = !needsJson && trackedVolumes === 0;

  useEffect(() => {
    if (!isAuthenticated) {
      didAutoRouteRef.current = false;
      didAutoOpenSetupRef.current = false;
      setSelectedKey("volumes");
      return;
    }
    if (didAutoRouteRef.current) {
      return;
    }
    setSelectedKey("volumes");
    didAutoRouteRef.current = true;
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!isAdmin) return;
    if (didAutoOpenSetupRef.current) return;
    if (!(needsJson || needsSync)) return;
    setSettingsOpen(true);
    didAutoOpenSetupRef.current = true;
  }, [isAuthenticated, isAdmin, needsJson, needsSync]);

  const menuItems = [
    {
      key: "volumes",
      icon: <DatabaseOutlined />,
      label: isWorker ? "My Volumes" : "Volume Tracker",
    },
    { key: "dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
    {
      key: "progress",
      icon: <TeamOutlined />,
      label: isAdmin ? "Team Progress" : "My Progress",
    },
    {
      key: "quotas",
      icon: <ScheduleOutlined />,
      label: isAdmin ? "Weekly Quotas" : "My Quota",
    },
    ...(isAdmin
      ? [
          {
            key: "model-quality",
            icon: <LineChartOutlined />,
            label: "Model Quality",
          },
        ]
      : []),
    { type: "divider" },
    {
      key: "issues",
      icon: <BugOutlined />,
      label: "Issues & Flags",
      disabled: true,
    },
  ];

  const renderSubView = () => {
    switch (selectedKey) {
      case "dashboard":
        return <AnnotationDashboard />;
      case "progress":
        return <ProofreaderProgress />;
      case "quotas":
        return <QuotaManagement />;
      case "volumes":
        return <VolumeTracker onOpenSettings={() => setSettingsOpen(true)} />;
      case "model-quality":
        return <ModelQualityDashboard />;
      default:
        return <VolumeTracker onOpenSettings={() => setSettingsOpen(true)} />;
    }
  };

  const projectLabel = projectInfo?.name || pmConfig?.project_name || "Project";
  const metadataLabel = pmConfig?.metadata_path
    ? pmConfig.metadata_path.split("/").pop()
    : "metadata not set";
  const dataRootLabel = pmConfig?.data_root
    ? pmConfig.data_root.split("/").pop() || pmConfig.data_root
    : "storage not set";

  const heroSummary = useMemo(() => {
    if (needsJson) {
      return "Open Settings to choose the project JSON.";
    }
    if (needsSync) {
      return "Settings are saved. Run storage sync next.";
    }
    return "Project is loaded. Use Volume Tracker for assignments and status.";
  }, [needsJson, needsSync]);

  if (!isAuthenticated) {
    return <ProjectManagerLogin />;
  }

  return (
    <Layout
      style={{
        height: "calc(100vh - 110px)",
        background: "#fff",
        borderRadius: 8,
        overflow: "hidden",
        border: "1px solid #f0f0f0",
      }}
    >
      <Sider
        width={240}
        theme="light"
        style={{
          borderRight: "1px solid #f0f0f0",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "16px 20px 12px" }}>
          <Title level={5} style={{ margin: 0 }}>
            Project Manager
          </Title>
          <Text type="secondary" style={{ fontSize: 11 }}>
            streamlined workflow
          </Text>
        </div>

        <div style={{ padding: "0 20px 16px" }}>
          <div
            style={{
              background: "#f9f9f9",
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid #f0f0f0",
            }}
          >
            <Space direction="vertical" size={0} style={{ width: "100%" }}>
              <Text strong style={{ fontSize: 13, display: "block" }}>
                {user?.name}
              </Text>
              <Space align="center" style={{ marginTop: 2 }}>
                <Tag
                  color={isAdmin ? "gold" : "blue"}
                  style={{ margin: 0, fontSize: 10, borderRadius: 4 }}
                >
                  {isAdmin ? "ADMIN" : "WORKER"}
                </Tag>
                <Button
                  type="link"
                  size="small"
                  onClick={logout}
                  style={{ padding: 0, fontSize: 11, height: "auto" }}
                >
                  Sign Out
                </Button>
              </Space>
            </Space>
          </div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          onClick={(e) => setSelectedKey(e.key)}
          items={menuItems}
          style={{ borderRight: 0, flex: 1 }}
        />
      </Sider>

      <Content
        style={{ padding: "24px", overflow: "auto", background: "#fff" }}
      >
        <Card
          size="small"
          style={{ marginBottom: 16, background: "#fcfcfc" }}
          styles={{ body: { padding: "16px" } }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <Space direction="vertical" size={6}>
              <Title level={4} style={{ margin: 0 }}>
                {projectLabel}
              </Title>
              <Text type="secondary">{heroSummary}</Text>
              <Space wrap size={[8, 8]}>
                <Tag color="blue" style={{ margin: 0 }}>
                  {trackedVolumes} volumes
                </Tag>
                <Tag style={{ margin: 0 }}>{metadataLabel}</Tag>
                <Tag style={{ margin: 0 }}>{dataRootLabel}</Tag>
              </Space>
            </Space>
            <Space wrap>
              <Button
                size="small"
                icon={<SettingOutlined />}
                onClick={() => setSettingsOpen(true)}
              >
                Settings
              </Button>
              {isAdmin && (
                <Button
                  size="small"
                  type="primary"
                  icon={<SyncOutlined />}
                  onClick={ingestData}
                  loading={loading}
                >
                  Sync
                </Button>
              )}
            </Space>
          </div>
        </Card>
        {renderSubView()}
        <Modal
          title={isAdmin ? "Project Settings" : "Project Info"}
          open={settingsOpen}
          onCancel={() => setSettingsOpen(false)}
          footer={null}
          width={920}
          destroyOnClose={false}
        >
          <ProjectSourceSettings
            isModal
            onOpenVolumes={() => {
              setSettingsOpen(false);
              setSelectedKey("volumes");
            }}
          />
        </Modal>
      </Content>
    </Layout>
  );
};

const ProjectManager = () => (
  <ConfigProvider
    theme={{
      components: {
        Layout: { siderBg: "#fafafa" },
        Menu: { itemBg: "#fafafa" },
      },
    }}
  >
    <ProjectManagerProvider>
      <ProjectManagerInner />
    </ProjectManagerProvider>
  </ConfigProvider>
);

export default ProjectManager;
