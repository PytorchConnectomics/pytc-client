import React, { useState } from "react";
import DataLoader from "./DataLoader";
import Visualization from "../views/Visualization";
import ModelTraining from "../views/ModelTraining";
import ModelInference from "../views/ModelInference";
import Monitoring from "../views/Monitoring";
import { Layout, Menu } from "antd";
import { getNeuroglancerViewer } from "../utils/api";

const { Content, Sider } = Layout;

function Views() {
  const [current, setCurrent] = useState("visualization");
  const [viewers, setViewers] = useState([]);
  console.log(viewers);

  const onClick = (e) => {
    setCurrent(e.key);
  };

  const items = [
    { label: "Visualization", key: "visualization" },
    { label: "Model Training", key: "training" },
    { label: "Model Inference", key: "inference" },
    { label: "Tensorboard", key: "monitoring" },
  ];

  const renderMenu = () => {
    if (current === "visualization") {
      return <Visualization viewers={viewers} setViewers={setViewers} />;
    } else if (current === "training") {
      return <ModelTraining />;
    } else if (current === "monitoring") {
      return <Monitoring />;
    } else if (current === "inference") {
      return <ModelInference />;
    }
  };

  const [collapsed, setCollapsed] = useState(false);

  const fetchNeuroglancerViewer = async (
    currentImage,
    currentLabel,
    scales
  ) => {
    try {
      const exists = viewers.find(
        (viewer) => viewer.key === currentImage.uid + currentLabel.uid
      );
      console.log(exists, viewers);
      if (!exists) {
        const res = await getNeuroglancerViewer(
          currentImage,
          currentLabel,
          scales
        );
        console.log(res);

        setViewers([
          ...viewers,
          {
            key: currentImage.uid + currentLabel.uid,
            title: currentImage.name + " & " + currentLabel.name,
            viewer: res,
          },
        ]);
      }
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
        // collapsible
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
