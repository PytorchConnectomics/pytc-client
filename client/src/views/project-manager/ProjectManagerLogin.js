import React, { useState } from "react";
import { Card, Form, Input, Button, Typography, Space, Divider } from "antd";
import { UserOutlined, LockOutlined, RocketOutlined } from "@ant-design/icons";
import { useProjectManager } from "../../contexts/ProjectManagerContext";

const { Title, Text } = Typography;

export default function ProjectManagerLogin() {
  const { login } = useProjectManager();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values) => {
    setLoading(true);
    const success = await login(values.username, values.password);
    setLoading(false);
  };

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#f0f2f5",
        padding: 24,
      }}
    >
      <Card
        style={{
          width: 400,
          borderRadius: 12,
          boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
          border: "none",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              margin: "0 auto 16px",
              color: "#fff",
              fontSize: 32,
              boxShadow: "0 4px 12px rgba(24,144,255,0.3)",
            }}
          >
            <RocketOutlined />
          </div>
          <Title level={3} style={{ margin: 0 }}>
            Project Manager
          </Title>
          <Text type="secondary">Sign in to manage EM connectomics tasks</Text>
        </div>

        <Form
          name="pm_login"
          initialValues={{ remember: true }}
          onFinish={onFinish}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: "Please input your username!" }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: "rgba(0,0,0,.25)" }} />}
              placeholder="Username"
              style={{ borderRadius: 8 }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: "Please input your password!" }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: "rgba(0,0,0,.25)" }} />}
              placeholder="Password"
              style={{ borderRadius: 8 }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                height: 48,
                borderRadius: 8,
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              Login
            </Button>
          </Form.Item>
        </Form>

        <Divider plain>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Login Credentials
          </Text>
        </Divider>

        <div
          style={{
            background: "#fafafa",
            padding: "8px 16px",
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          <Space direction="vertical" size={2}>
            <Text type="secondary">
              Admin Access: <Text code>admin / admin123</Text>
            </Text>
            <Text type="secondary">
              Annotator Access: <Text code>alex / alex123</Text>
            </Text>
          </Space>
        </div>
      </Card>
    </div>
  );
}
