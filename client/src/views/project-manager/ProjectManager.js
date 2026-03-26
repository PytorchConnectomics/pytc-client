import React, { useState } from "react";
import {
  Layout,
  Menu,
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
  UserOutlined,
  CrownOutlined,
} from "@ant-design/icons";

import AnnotationDashboard from "./AnnotationDashboard";
import ProofreaderProgress from "./ProofreaderProgress";
import QuotaManagement from "./QuotaManagement";
import ModelQualityDashboard from "./ModelQualityDashboard";
import VolumeTracker from "./VolumeTracker";
import ProjectManagerLogin from "./ProjectManagerLogin";
import {
  ProjectManagerProvider,
  useProjectManager,
} from "../../contexts/ProjectManagerContext";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

const ProjectManagerInner = () => {
  const { isAuthenticated, user, logout, isAdmin, isWorker, loading } =
    useProjectManager();

  const [selectedKey, setSelectedKey] = useState("dashboard");

  // ── Login Gate ────────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    return <ProjectManagerLogin />;
  }

  // ── Menu items ────────────────────────────────────────────────────────────
  const menuItems = [
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
    {
      key: "volumes",
      icon: <DatabaseOutlined />,
      label: isWorker ? "My Volumes" : "Volume Tracker",
    },
    // Admin-only items
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
    {
      key: "settings",
      icon: <SettingOutlined />,
      label: "Settings",
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
        return <VolumeTracker />;
      case "model-quality":
        return <ModelQualityDashboard />;
      default:
        return <AnnotationDashboard />;
    }
  };

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
        {/* ── Brand header ── */}
        <div style={{ padding: "16px 20px 12px" }}>
          <Title level={5} style={{ margin: 0 }}>
            Project Manager
          </Title>
          <Text type="secondary" style={{ fontSize: 11 }}>
            v2.0 · seg.bio
          </Text>
        </div>

        {/* ── User Profile & Role Tag ── */}
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

        {/* ── Navigation ── */}
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
        {renderSubView()}
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
