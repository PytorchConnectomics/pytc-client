import React, { useState } from "react";
import DataLoader from "./DataLoader";
import Visualization from "../views/Visualization";
import ModelTraining from "../views/ModelTraining";
import Monitoring from "../views/Monitoring";
import ModelInference from "../views/ModelInference";
import { Layout, Menu, theme } from "antd";
import { getNeuroglancerViewer } from "../utils/api";

const { Header, Content, Footer, Sider } = Layout;

function Views() {
  const [current, setCurrent] = useState("vis");
  const [viewer, setViewer] = useState(null);
  const onClick = (e) => {
    setCurrent(e.key);
  };
  const items = [
    { label: "Visualization", key: "vis" },
    { label: "Model Training", key: "train" },
    { label: "Model Inference", key: "inference" },
    { label: "Tensorboard", key: "monitor" },
  ];
  const renderMenu = () => {
    if (current === "vis") {
      return <Visualization viewer={viewer} />;
    } else if (current === "train") {
      return <ModelTraining />;
    } else if (current === "monitor") {
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
      setViewer(res);
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
        {/*<div*/}
        {/*  style={{*/}
        {/*    height: 32,*/}
        {/*    margin: 16,*/}
        {/*    background: "rgba(255, 255, 255, 0.2)",*/}
        {/*  }}*/}
        {/*/>*/}
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
