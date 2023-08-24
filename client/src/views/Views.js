import React, { useState } from "react";
import DataLoader from "./DataLoader";
import Visualization from "../views/Visualization";
import ModelTraining from "../views/ModelTraining";
import ModelInference from "../views/ModelInference";
import Monitoring from "../views/Monitoring";
import GettingStarted from "../views/GettingStarted";
import { Layout, Menu, theme } from "antd";
import { getNeuroglancerViewer } from "../utils/api";

const { Header, Content, Footer, Sider } = Layout;

function Views() {
  const [current, setCurrent] = useState("gettingStarted");
  const [viewers, setViewers] = useState([]);
  console.log(viewers);

  const onClick = (e) => {
    setCurrent(e.key);
  };

  const items = [
    { label: "Getting Started", key: "gettingStarted" },
    { label: "Visualization", key: "visualization" },
    { label: "Model Training", key: "training" },
    { label: "Model Inference", key: "inference" },
    { label: "Tensorboard", key: "monitoring" },
  ];

  const renderMenu = () => {
    if (current === "gettingStarted") {
      return <GettingStarted />;
    } else if (current === "visualization") {
      return <Visualization viewers={viewers} />;
    } else if (current === "training") {
      return <ModelTraining />;
    } else if (current === "monitoring") {
      return <Monitoring />;
    } else if (current === "inference") {
      return <ModelInference />;
    }
  };

  const [collapsed, setCollapsed] = useState(false);

  const {
    token: { colorBgContainer },
  } = theme.useToken();

  const fetchNeuroglancerViewer = async (
    currentImage,
    currentLabel,
    currentImagePath,
    currentLabelPath
  ) => {
    try {
      const res = await getNeuroglancerViewer(
        currentImage,
        currentLabel,
        currentImagePath,
        currentLabelPath
      );
      console.log(res);

      // check currentIamge.name is exist in viewers
      setViewers([
        ...viewers,
        {
          key: res,
          title: currentImage.name,
          viewer: res,
        },
      ]);
    } catch (e) {
      console.log(e);
    }
  };

  return (
    <Layout
      style={{
        minHeight: "99vh",
        minWidth: "90vw",
      }}
    >
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={(value) => setCollapsed(value)}
        theme="light"
        collapsedWidth="0"
      >
        <DataLoader fetchNeuroglancerViewer={fetchNeuroglancerViewer} />
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
