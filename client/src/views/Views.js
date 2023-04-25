import React, { useState } from "react";
import Dataloader from "../views/Dataloader";
import Visualization from "../views/Visualization";
import ModelTraining from "../views/ModelTraining";
import { Layout, Menu, theme } from "antd";
const { Header, Content, Footer, Sider } = Layout;

function Views() {
  const [current, setCurrent] = useState("vis");
  const onClick = (e) => {
    setCurrent(e.key);
  };
  const items = [
    { label: "Visualization", key: "vis" },
    { label: "Model Training", key: "train" },
  ];
  const renderMenu = () => {
    if (current === "vis") {
      return <Visualization />;
    } else if (current === "train") {
      return <ModelTraining />;
    }
  };

  const [collapsed, setCollapsed] = useState(false);
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  return (
    <Layout
      style={{
        minHeight: "100vh",
      }}
    >
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={(value) => setCollapsed(value)}
        theme="light"
        collapsedWidth="0"
      >
        <div
          style={{
            height: 32,
            margin: 16,
            background: "rgba(255, 255, 255, 0.2)",
          }}
        />
        <Dataloader />
      </Sider>
      <Layout className="site-layout">
        <Content
          style={{
            margin: "0 16px",
          }}
        >
          <Menu
            onClick={onClick}
            selectedKeys={[current]}
            mode="horizontal"
            items={items}
          />
          {renderMenu()}
        </Content>
      </Layout>
    </Layout>
  );
}

export default Views;
