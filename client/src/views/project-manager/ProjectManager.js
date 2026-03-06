import React, { useState } from "react";
import { Layout, Menu, Typography, ConfigProvider } from "antd";
import {
    DashboardOutlined,
    TeamOutlined,
    ScheduleOutlined,
    LineChartOutlined,
    BugOutlined,
    GlobalOutlined,
    SettingOutlined,
} from "@ant-design/icons";

import AnnotationDashboard from "./AnnotationDashboard";
import ProofreaderProgress from "./ProofreaderProgress";
import QuotaManagement from "./QuotaManagement";
import ModelQualityDashboard from "./ModelQualityDashboard";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

const ProjectManager = () => {
    const [selectedKey, setSelectedKey] = useState("dashboard");

    const menuItems = [
        {
            key: "dashboard",
            icon: <DashboardOutlined />,
            label: "Dashboard",
        },
        {
            key: "progress",
            icon: <TeamOutlined />,
            label: "Proofreader Progress",
        },
        {
            key: "quotas",
            icon: <ScheduleOutlined />,
            label: "Weekly Quotas",
        },
        {
            key: "model-quality",
            icon: <LineChartOutlined />,
            label: "Model Quality",
        },
        {
            type: "divider",
        },
        {
            key: "issues",
            icon: <BugOutlined />,
            label: "Issues & Flags",
            disabled: true,
        },
        {
            key: "global-quality",
            icon: <GlobalOutlined />,
            label: "Global Quality",
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
            case "model-quality":
                return <ModelQualityDashboard />;
            default:
                return <AnnotationDashboard />;
        }
    };

    return (
        <ConfigProvider
            theme={{
                components: {
                    Layout: {
                        siderBg: "#fafafa",
                    },
                    Menu: {
                        itemBg: "#fafafa",
                    },
                },
            }}
        >
            <Layout style={{ height: "calc(100vh - 110px)", background: "#fff", borderRadius: 8, overflow: "hidden", border: "1px solid #f0f0f0" }}>
                <Sider width={240} theme="light" style={{ borderRight: "1px solid #f0f0f0" }}>
                    <div style={{ padding: "16px 24px" }}>
                        <Title level={5} style={{ margin: 0 }}>Project Manager</Title>
                        <Text type="secondary" style={{ fontSize: 11 }}>v1.0.4-beta</Text>
                    </div>
                    <Menu
                        mode="inline"
                        selectedKeys={[selectedKey]}
                        onClick={(e) => setSelectedKey(e.key)}
                        items={menuItems}
                        style={{ borderRight: 0 }}
                    />
                </Sider>
                <Content style={{ padding: "24px", overflow: "auto", background: "#fff" }}>
                    {renderSubView()}
                </Content>
            </Layout>
        </ConfigProvider>
    );
};

export default ProjectManager;
